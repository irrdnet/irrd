# flake8: noqa: W293
import sys

import os
import signal
import socket
import sqlalchemy as sa
import subprocess
import textwrap
import yaml
from alembic import command, config
from typing import List

from irrd.conf import config_init
from irrd.utils.rpsl_samples import SAMPLE_MNTNER, SAMPLE_PERSON
from .data import EMAIL_SMTP_PORT, EMAIL_RETURN_MSGS_COMMAND, EMAIL_SEPARATOR

IRRD_ROOT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
sys.path.append(IRRD_ROOT_PATH)


class TestIntegration:
    """
    Note that this test will not be included in the default py.test discovery,
    this is intentional.
    """
    def test_irrd_integration(self, tmpdir):
        # IRRD_DATABASE_URL overrides the yaml config, so should be removed
        del os.environ['IRRD_DATABASE_URL']
        # PYTHONPATH needs to contain the twisted plugin path.
        os.environ['PYTHONPATH'] = IRRD_ROOT_PATH
        os.environ['IRRD_SCHEDULER_TIMER_OVERRIDE'] = '1'
        self.tmpdir = tmpdir

        self._start_mailserver()
        self._start_irrds()

        self._submit_update(self.config_path1,
                            SAMPLE_MNTNER + '\n\n' + SAMPLE_PERSON + '\n\npassword: md5-password')
        mails = self._retrieve_mails()
        assert len(mails) == 1
        assert b'\nSubject: SUCCESS: my subject\n' in mails[0]
        assert b'\nFrom: from@example.com\n' in mails[0]
        assert b'\nTo: Sasha <sasha@example.com>\n' in mails[0]
        assert b'Create succeeded: [mntner] TEST-MNT' in mails[0]
        assert b'Create succeeded: [person] PERSON-TEST' in mails[0]
        assert b'email footer' in mails[0]
        assert b'Generated by IRRd version ' in mails[0]
        
    def _start_mailserver(self):
        self.pidfile_mailserver = str(self.tmpdir) + '/mailserver.pid'
        self.logfile_mailserver = str(self.tmpdir) + '/mailserver.log'
        mailserver_path = IRRD_ROOT_PATH + '/irrd/integration_tests/mailserver.tac'
        assert not subprocess.call(['twistd', f'--pidfile={self.pidfile_mailserver}',
                                    f'--logfile={self.logfile_mailserver}', '-y', mailserver_path])

    # noinspection PyTypeChecker
    def _start_irrds(self):
        self.database_url1 = os.environ['IRRD_DATABASE_URL_INTEGRATION_1']
        self.database_url2 = os.environ['IRRD_DATABASE_URL_INTEGRATION_2']

        self.config_path1 = str(self.tmpdir) + '/irrd1_config.yaml'
        self.config_path2 = str(self.tmpdir) + '/irrd2_config.yaml'
        self.logfile1 = str(self.tmpdir) + '/irrd1.log'
        self.logfile2 = str(self.tmpdir) + '/irrd2.log'
        self.pidfile1 = str(self.tmpdir) + '/irrd1.pid'
        self.pidfile2 = str(self.tmpdir) + '/irrd2.pid'
        self.export_dir1 = str(self.tmpdir) + '/export1/'
        self.export_dir2 = str(self.tmpdir) + '/export1/'

        self.port_http1 = 6080
        self.port_whois1 = 6043
        self.port_http2 = 6081
        self.port_whois2 = 6044

        print(textwrap.dedent(f"""
            Preparing to start IRRd for integration test.
            
            IRRd #1 running on HTTP port {self.port_http1}, whois port {self.port_whois1}
            Config in: {self.config_path1}
            Database URL: {self.database_url1}
            PID file: {self.pidfile1}
            Logfile: {self.logfile1}

            IRRd #2 running on HTTP port {self.port_http2}, whois port {self.port_whois2}
            Config in: {self.config_path2}
            Database URL: {self.database_url2}
            PID file: {self.pidfile2}
            Logfile: {self.logfile2}
        """))

        base_config = {
            'irrd': {
                'access_lists': {
                    'localhost': ['::/32', '127.0.0.1']
                },

                'server': {
                    'http': {
                        'access_list': 'localhost',
                        'interface': '::0',
                        'port': 8080
                    },
                    'whois': {
                        'interface': '::0',
                        'max_connections': 50,
                        'port': 8043
                    },
                },

                'auth': {
                    'gnupg_keyring': None,
                    'override_password': None,
                },

                'email': {
                    'footer': 'email footer',
                    'from': 'from@example.com',
                    'smtp': f'localhost:{EMAIL_SMTP_PORT}',
                },

                'log': {
                    'logfile_path': None,
                    'loglevel': 'DEBUG'
                },

                'sources': {}
            }
        }

        config1 = base_config.copy()
        config1['irrd']['database_url'] = self.database_url1
        config1['irrd']['server']['http']['port'] = self.port_http1
        config1['irrd']['server']['whois']['port'] = self.port_whois1
        config1['irrd']['auth']['gnupg_keyring'] = str(self.tmpdir) + '/gnupg1'
        config1['irrd']['log']['logfile_path'] = self.logfile1
        config1['irrd']['sources']['TEST'] = {
            'authoritative': True,
            'keep_journal': True,
            'export_destination': self.export_dir1,
            'export_timer': '1',
            'nrtm_access_list': 'localhost',
        }
        with open(self.config_path1, 'w') as yaml_file:
            yaml.safe_dump(config1, yaml_file)

        config2 = base_config.copy()
        config2['irrd']['database_url'] = self.database_url2
        config2['irrd']['server']['http']['port'] = self.port_http2
        config2['irrd']['server']['whois']['port'] = self.port_whois2
        config2['irrd']['auth']['gnupg_keyring'] = str(self.tmpdir) + '/gnupg2'
        config2['irrd']['log']['logfile_path'] = self.logfile2
        config2['irrd']['sources']['TEST'] = {
            'keep_journal': True,
            'import_serial_source': f'file://{self.export_dir1}/TEST.CURRENTSERIAL',
            'import_source': f'file://{self.export_dir1}/test.db.gz',
            'export_destination': self.export_dir2,
            'import_timer': '1',
            'export_timer': '1',
            'nrtm_host': '127.0.0.1',
            'nrtm_port': str(self.port_whois1),
            'nrtm_access_list': 'localhost',
        }
        with open(self.config_path2, 'w') as yaml_file:
            yaml.safe_dump(config2, yaml_file)

        self._prepare_database()

        assert not subprocess.call(['twistd', f'--pidfile={self.pidfile1}', 'irrd', f'--config={self.config_path1}'])
        # assert not subprocess.call(['twistd', f'--pidfile={self.pidfile2}', 'irrd', f'--config={self.config_path2}'])

    def _prepare_database(self):
        config_init(self.config_path1)
        alembic_cfg = config.Config()
        alembic_cfg.set_main_option('script_location', f'{IRRD_ROOT_PATH}/irrd/storage/alembic')
        command.upgrade(alembic_cfg, 'head')

        connection = sa.create_engine(self.database_url1).connect()
        connection.execute('DELETE FROM rpsl_objects')
        connection.execute('DELETE FROM rpsl_database_journal')
        connection.execute('DELETE FROM database_status')

        config_init(self.config_path2)
        alembic_cfg = config.Config()
        alembic_cfg.set_main_option('script_location', f'{IRRD_ROOT_PATH}/irrd/storage/alembic')
        command.upgrade(alembic_cfg, 'head')

        connection = sa.create_engine(self.database_url2).connect()
        connection.execute('DELETE FROM rpsl_objects')
        connection.execute('DELETE FROM rpsl_database_journal')
        connection.execute('DELETE FROM database_status')

    def _submit_update(self, config_path, request):
        email = textwrap.dedent("""
            From submitter@example.com@localhost  Thu Jan  5 10:04:48 2018
            Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
              by hostname (Postfix) with ESMTPS id 740AD310597
              for <irrd@example.com>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
            Message-ID: <1325754288.4989.6.camel@hostname>
            Subject: my subject
            Subject: not my subject
            From: Sasha <sasha@example.com>
            To: sasha@localhost
            Date: Thu, 05 Jan 2018 10:04:48 +0100
            Content-Type: text/plain; charset=us-ascii
            X-Mailer: Python 3.7
            Content-Transfer-Encoding: 7bit
            Mime-Version: 1.0

        """).lstrip().encode('ascii')
        email += request.encode('ascii')

        script = IRRD_ROOT_PATH + '/irrd/scripts/submit_email.py'
        p = subprocess.Popen([script, f'--config={config_path}'], stdin=subprocess.PIPE)
        p.communicate(email)
        p.wait()

    def _retrieve_mails(self) -> List[bytes]:
        s = socket.socket()
        s.settimeout(5)
        s.connect(('localhost', EMAIL_SMTP_PORT))

        s.sendall(f'{EMAIL_RETURN_MSGS_COMMAND}\r\n'.encode('ascii'))
        data = s.recv(1024*1024)
        data = data.split(b'\n', 1)[1]
        return [m.strip() for m in data.split(EMAIL_SEPARATOR.encode('ascii'))]

    def teardown_method(self, method):
        for pidfile in self.pidfile1, self.pidfile2, self.pidfile_mailserver:
            try:
                with open(pidfile) as fh:
                    os.kill(int(fh.read()), signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError, ValueError):
                pass
