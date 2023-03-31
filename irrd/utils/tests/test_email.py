# flake8: noqa: W291, W293

import textwrap
from unittest.mock import Mock

import pytest

from irrd.conf import get_setting

from ..email import EmailParser, send_email


class TestEmailParser:
    # These tests do not mock utils.pgp.validate_pgp_signature, and have quite
    # some overlap with the tests for that part. This is on purpose, as PGP
    # validation and MIME parsing can be tricky, and errors in either part or
    # their coupling easily cause security issues.

    def test_parse_valid_plain_with_charset(self):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
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

        message content
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body == "message content"
        assert parser.message_id == "<1325754288.4989.6.camel@hostname>"
        assert parser.message_from == "Sasha <sasha@example.com>"
        assert parser.message_date == "Thu, 05 Jan 2018 10:04:48 +0100"
        assert parser.message_subject == "my subject"
        assert parser.pgp_fingerprint is None

    def test_parse_valid_plain_without_charset(self):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: text/plain
        X-Mailer: Python 3.7
        Content-Transfer-Encoding: 7bit
        Mime-Version: 1.0

        message content
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body == "message content"
        assert parser.pgp_fingerprint is None

    def test_parse_valid_multipart_text_plain_with_charset(self):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/alternative;
         boundary="Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)
        
        
        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F
        Content-Transfer-Encoding: 7bit
        Content-Type: text/plain;
            charset=us-ascii
        
        test 1 2 3
        
        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F
        Content-Transfer-Encoding: 7bit
        Content-Type: text/html;
            charset=us-ascii
        
        <html><head><meta http-equiv="Content-Type" content="text/html charset=us-ascii"></head><body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;" class=""><b class="">test 1 2 3</b><div class=""><br class=""></div></body></html>
        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F--
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body.strip() == "test 1 2 3"
        assert parser.pgp_fingerprint is None

    def test_parse_valid_multipart_quoted_printable_with_charset(self):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/alternative;
         boundary="Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)


        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F
        Content-Type: text/plain;
            charset="utf-8"
        Content-Transfer-Encoding: quoted-printable
        se font =
        vite p=C3=A9dagogues


        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F
        Content-Transfer-Encoding: 7bit
        Content-Type: text/html;
            charset=us-ascii

        <html><head><meta http-equiv="Content-Type" content="text/html charset=us-ascii"></head><body style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;" class=""><b class="">test 1 2 3</b><div class=""><br class=""></div></body></html>
        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F--
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body.strip() == "se font vite pédagogues"
        assert parser.pgp_fingerprint is None

    def test_parse_valid_multipart_quoted_printable_without_charset(self):
        # latin-1 will be assumed
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/alternative;
         boundary="Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)


        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F
        Content-Type: text/plain
        Content-Transfer-Encoding: quoted-printable
        
        se=20font =
        vite p=C3=A9dag=
        ogues


        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F
        Content-Transfer-Encoding: 7bit
        Content-Type: text/html;
            charset=us-ascii

        <html><head><meta http-equiv='Content-Type' content='text/html charset=us-ascii'></head><body style='word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;' class=""><b class="">test 1 2 3</b><div class=""><br class=""></div></body></html>
        --Apple-Mail=_01FE5B2D-C7F3-4DDD-AB42-B92C88CFBF0F--
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body.strip() == "se font vite pdagogues"
        assert parser.pgp_fingerprint is None

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_parse_valid_multipart_signed_ascii(self, tmp_gpg_dir, preload_gpg_key):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/signed;
         boundary="Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)
        
        
        --Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25
        Content-Transfer-Encoding: 7bit
        Content-Type: text/plain;
        \tcharset=us-ascii
        
        test 1 2 3
        
        --Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25
        Content-Transfer-Encoding: 7bit
        Content-Disposition: attachment;
            filename=signature.asc
        Content-Type: application/pgp-signature;
            name=signature.asc
        Content-Description: Message signed with OpenPGP
        
        -----BEGIN PGP SIGNATURE-----
        
        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlthsw0ACgkQqDg7p4Dy
        OMbLdBAAnJ93CZYz6VNhHiSFhj2EtU6yG70chyAiCfrZXsXGWQXNBbkQBCpk3Cy0
        HD2cIBxh1612bDkct8ezWaS4uOEvp5gyEJg0/VrAMCvWIEXEFizE75kOgj3ay+hs
        Dj4C7TRlRvQdRbaNdCb3R27WMK9GPwDJgqjifZQu13pWkkAxQLpZBs+wbnWvh01X
        QWQdf7xr3PQUkm+uVE2fU7j+c1vQs5oJLMdvSuzSN59IvLiEmRFrkQF7yj3WCesh
        dTxAYl5TA8IhldXsc2/MYL24fNKk2L9Ns3Cr0x9XHYBk+w/iGQuCvTkTiOzeoxab
        puk83Xr+WDgVo6w6KT7n5ZFg7XRH/WV0hhdy6i+wuyXnwdTP5JQbJn66xZV4iYZh
        QAHrNeb/kRMcw7l6I3eL94W7ndfCZK7/XhHqYB4m88Jnbaklxih2gjJGWu50eQc7
        EXt0dl6BQeKlMtLWfgtBY4RzEglr1u99DSEqotJTlpSqUQ79rYwzKNvjI1Xc7yJc
        lLNwRJTtoWd8sUc0njlemxtVELNHUj0ahpQgMTqw1WbJu+FJxaTcRdbu6fYwl7hc
        k1Bt6Qyyn4qWD19aV6yClqyhJwZB2uoSKHvBmPIu31nHRYNr9SWD75dht8YODsmF
        QxtFWD7kfutDc40U0GjukbcPsfni1BH9AZZbUsm6YS7JMxoh1Rk=
        =92HM
        -----END PGP SIGNATURE-----
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body.strip() == "test 1 2 3"
        assert (
            parser._pgp_signature
            == textwrap.dedent(
                """
        -----BEGIN PGP SIGNATURE-----

        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlthsw0ACgkQqDg7p4Dy
        OMbLdBAAnJ93CZYz6VNhHiSFhj2EtU6yG70chyAiCfrZXsXGWQXNBbkQBCpk3Cy0
        HD2cIBxh1612bDkct8ezWaS4uOEvp5gyEJg0/VrAMCvWIEXEFizE75kOgj3ay+hs
        Dj4C7TRlRvQdRbaNdCb3R27WMK9GPwDJgqjifZQu13pWkkAxQLpZBs+wbnWvh01X
        QWQdf7xr3PQUkm+uVE2fU7j+c1vQs5oJLMdvSuzSN59IvLiEmRFrkQF7yj3WCesh
        dTxAYl5TA8IhldXsc2/MYL24fNKk2L9Ns3Cr0x9XHYBk+w/iGQuCvTkTiOzeoxab
        puk83Xr+WDgVo6w6KT7n5ZFg7XRH/WV0hhdy6i+wuyXnwdTP5JQbJn66xZV4iYZh
        QAHrNeb/kRMcw7l6I3eL94W7ndfCZK7/XhHqYB4m88Jnbaklxih2gjJGWu50eQc7
        EXt0dl6BQeKlMtLWfgtBY4RzEglr1u99DSEqotJTlpSqUQ79rYwzKNvjI1Xc7yJc
        lLNwRJTtoWd8sUc0njlemxtVELNHUj0ahpQgMTqw1WbJu+FJxaTcRdbu6fYwl7hc
        k1Bt6Qyyn4qWD19aV6yClqyhJwZB2uoSKHvBmPIu31nHRYNr9SWD75dht8YODsmF
        QxtFWD7kfutDc40U0GjukbcPsfni1BH9AZZbUsm6YS7JMxoh1Rk=
        =92HM
        -----END PGP SIGNATURE-----"""
            ).strip()
        )
        assert parser.pgp_fingerprint == "86261D8DBEBDA4F54692D64DA8383BA780F238C6"

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_parse_invalid_multipart_signed_ascii_with_additional_text_part(
        self, tmp_gpg_dir, preload_gpg_key
    ):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/signed;
         boundary="Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)


        --Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25
        Content-Transfer-Encoding: 7bit
        Content-Type: text/plain;
        \tcharset=us-ascii

        test 1 2 3

        --Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25
        Content-Transfer-Encoding: 7bit
        Content-Disposition: attachment;
            filename=signature.asc
        Content-Type: application/pgp-signature;
            name=signature.asc
        Content-Description: Message signed with OpenPGP

        -----BEGIN PGP SIGNATURE-----

        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlthsw0ACgkQqDg7p4Dy
        OMbLdBAAnJ93CZYz6VNhHiSFhj2EtU6yG70chyAiCfrZXsXGWQXNBbkQBCpk3Cy0
        HD2cIBxh1612bDkct8ezWaS4uOEvp5gyEJg0/VrAMCvWIEXEFizE75kOgj3ay+hs
        Dj4C7TRlRvQdRbaNdCb3R27WMK9GPwDJgqjifZQu13pWkkAxQLpZBs+wbnWvh01X
        QWQdf7xr3PQUkm+uVE2fU7j+c1vQs5oJLMdvSuzSN59IvLiEmRFrkQF7yj3WCesh
        dTxAYl5TA8IhldXsc2/MYL24fNKk2L9Ns3Cr0x9XHYBk+w/iGQuCvTkTiOzeoxab
        puk83Xr+WDgVo6w6KT7n5ZFg7XRH/WV0hhdy6i+wuyXnwdTP5JQbJn66xZV4iYZh
        QAHrNeb/kRMcw7l6I3eL94W7ndfCZK7/XhHqYB4m88Jnbaklxih2gjJGWu50eQc7
        EXt0dl6BQeKlMtLWfgtBY4RzEglr1u99DSEqotJTlpSqUQ79rYwzKNvjI1Xc7yJc
        lLNwRJTtoWd8sUc0njlemxtVELNHUj0ahpQgMTqw1WbJu+FJxaTcRdbu6fYwl7hc
        k1Bt6Qyyn4qWD19aV6yClqyhJwZB2uoSKHvBmPIu31nHRYNr9SWD75dht8YODsmF
        QxtFWD7kfutDc40U0GjukbcPsfni1BH9AZZbUsm6YS7JMxoh1Rk=
        =92HM
        -----END PGP SIGNATURE-----
        
        --Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25
        Content-Transfer-Encoding: 7bit
        Content-Type: text/plain;
        \tcharset=us-ascii

        additional text/plain part - not signed

        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body.strip() == "additional text/plain part - not signed"
        assert parser.pgp_fingerprint is None

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_parse_valid_inline_signed_ascii(self, tmp_gpg_dir, preload_gpg_key):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: text/plain
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)
        
        UNSIGNED TEXT TO BE IGNORED
        
        -----BEGIN PGP SIGNED MESSAGE-----
        Hash: SHA256
        
        test 1 2 3
        -----BEGIN PGP SIGNATURE-----
        
        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAltix/QACgkQqDg7p4Dy
        OMYTzA//buAOavyy5mShsCu8jlAyA9Y9PZWp4fc9I2Gnef/ESwmagr10KIBJpz3M
        qO85Oxml3kJDKXUUS5NLxUiVQnznErETbPYx04S3NLP8yRvFUV31x5D7WPwy7g0V
        1WDr4eDBB+Nk9ib7fBGhKosjODzPt/58xTCgcD25rPYF8ie3VzIv0KzgSQNC3jqE
        e4+eCS/IpPxoVEqfR7Dxt9j6Z7+ERcNkNYexX14IdOL+eldXlOgZgAjhDyY1FGoX
        yZUBK1ZBXfyNY33dSMsM/LRN3TnnLeqQu4VlsgaE3syqgiHw3fLjnldAVFRaDV9g
        BTFg/3LQ+QwjzKcKi+f2pjr/FbsqnSBZZH31M6Pmdwvz9roZJB59Hhjgr+kxpfop
        bgZ95P4z2i7XuCOJmI5LNOaqlZmt3RebLd2QIAfKONi2GfwLl4ibk6VlCdMIQoJS
        paQ7V2Dq9r6Pure2wn+xIPOuySQ+zVf7emY9GFxFim87Eu2aaV4E/S52EpOFqWCU
        TgTCi98X5RJyBdvii7XBl+VcM041hww221nw2WvRECaImgwx1eNx2UjXpsLN5VrT
        oxZBbe2zPrzKJSG3WmBRi8bekarDrCPSd1uWXRoCqUmIPLTTID52ikkPKEBTeNyv
        4Ni0aIkkZY3cM0QR9EEHSCJgS2RVQujw/KZTeTQTLAJLtGtLbq8=
        =Zn24
        -----END PGP SIGNATURE-----
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body.strip() == "test 1 2 3"
        assert parser.pgp_fingerprint == "86261D8DBEBDA4F54692D64DA8383BA780F238C6"

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_parse_invalid_inline_signed_ascii_multiple_messages(self, tmp_gpg_dir, preload_gpg_key):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: text/plain
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)

        -----BEGIN PGP SIGNED MESSAGE-----
        Hash: SHA256

        test 1 2 3
        -----BEGIN PGP SIGNATURE-----

        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAltix/QACgkQqDg7p4Dy
        OMYTzA//buAOavyy5mShsCu8jlAyA9Y9PZWp4fc9I2Gnef/ESwmagr10KIBJpz3M
        qO85Oxml3kJDKXUUS5NLxUiVQnznErETbPYx04S3NLP8yRvFUV31x5D7WPwy7g0V
        1WDr4eDBB+Nk9ib7fBGhKosjODzPt/58xTCgcD25rPYF8ie3VzIv0KzgSQNC3jqE
        e4+eCS/IpPxoVEqfR7Dxt9j6Z7+ERcNkNYexX14IdOL+eldXlOgZgAjhDyY1FGoX
        yZUBK1ZBXfyNY33dSMsM/LRN3TnnLeqQu4VlsgaE3syqgiHw3fLjnldAVFRaDV9g
        BTFg/3LQ+QwjzKcKi+f2pjr/FbsqnSBZZH31M6Pmdwvz9roZJB59Hhjgr+kxpfop
        bgZ95P4z2i7XuCOJmI5LNOaqlZmt3RebLd2QIAfKONi2GfwLl4ibk6VlCdMIQoJS
        paQ7V2Dq9r6Pure2wn+xIPOuySQ+zVf7emY9GFxFim87Eu2aaV4E/S52EpOFqWCU
        TgTCi98X5RJyBdvii7XBl+VcM041hww221nw2WvRECaImgwx1eNx2UjXpsLN5VrT
        oxZBbe2zPrzKJSG3WmBRi8bekarDrCPSd1uWXRoCqUmIPLTTID52ikkPKEBTeNyv
        4Ni0aIkkZY3cM0QR9EEHSCJgS2RVQujw/KZTeTQTLAJLtGtLbq8=
        =Zn24
        -----END PGP SIGNATURE-----

        -----BEGIN PGP SIGNED MESSAGE-----
        Hash: SHA256

        INVALID
        -----BEGIN PGP SIGNATURE-----

        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAltix/QACgkQqDg7p4Dy
        OMYTzA//buAOavyy5mShsCu8jlAyA9Y9PZWp4fc9I2Gnef/ESwmagr10KIBJpz3M
        qO85Oxml3kJDKXUUS5NLxUiVQnznErETbPYx04S3NLP8yRvFUV31x5D7WPwy7g0V
        1WDr4eDBB+Nk9ib7fBGhKosjODzPt/58xTCgcD25rPYF8ie3VzIv0KzgSQNC3jqE
        e4+eCS/IpPxoVEqfR7Dxt9j6Z7+ERcNkNYexX14IdOL+eldXlOgZgAjhDyY1FGoX
        yZUBK1ZBXfyNY33dSMsM/LRN3TnnLeqQu4VlsgaE3syqgiHw3fLjnldAVFRaDV9g
        BTFg/3LQ+QwjzKcKi+f2pjr/FbsqnSBZZH31M6Pmdwvz9roZJB59Hhjgr+kxpfop
        bgZ95P4z2i7XuCOJmI5LNOaqlZmt3RebLd2QIAfKONi2GfwLl4ibk6VlCdMIQoJS
        paQ7V2Dq9r6Pure2wn+xIPOuySQ+zVf7emY9GFxFim87Eu2aaV4E/S52EpOFqWCU
        TgTCi98X5RJyBdvii7XBl+VcM041hww221nw2WvRECaImgwx1eNx2UjXpsLN5VrT
        oxZBbe2zPrzKJSG3WmBRi8bekarDrCPSd1uWXRoCqUmIPLTTID52ikkPKEBTeNyv
        4Ni0aIkkZY3cM0QR9EEHSCJgS2RVQujw/KZTeTQTLAJLtGtLbq8=
        =Zn24
        -----END PGP SIGNATURE-----
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.pgp_fingerprint is None

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_parse_valid_multipart_signed_unicode(self, tmp_gpg_dir, preload_gpg_key):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/signed;
         boundary="Apple-Mail=_18B291D9-548C-4458-8F17-B76537227FDF"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)


        --Apple-Mail=_18B291D9-548C-4458-8F17-B76537227FDF
        Content-Transfer-Encoding: base64
        Content-Type: text/plain;
        \tcharset=utf-8
        
        dGVzdCDwn5KpIMOpIMOmDQo=
        --Apple-Mail=_18B291D9-548C-4458-8F17-B76537227FDF
        Content-Transfer-Encoding: 7bit
        Content-Disposition: attachment;
            filename=signature.asc
        Content-Type: application/pgp-signature;
            name=signature.asc
        Content-Description: Message signed with OpenPGP
        
        -----BEGIN PGP SIGNATURE-----
        
        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlthw8cACgkQqDg7p4Dy
        OMZxpg//WFoLn70I4/VqAp0iTkqqxR9jQZ+7T6bvcGGnrHLdfmlplPjkkZ13dg9j
        LMyjxFJobm+TjqCyvHj8v2TpneGQv8tl8vOS2lBDnr99N0QROkf8MZdoQwfFPur4
        AuE5NpXQHjOuRzN7/a/CsGuh5yzg/srHRgBFlEGzpmlHJ/YpaNXaFPIkZY988ObJ
        +teJvhpN6qhXG2Nod8uDawOoZjmkUkyNWyNeEv0JgzvEuum1HSdY+hjJnmAZB1o8
        m5cRULei5JnsENEehC8otfyvp3hhlMrCF37jHCOtd7IZ0fbG/43PuJyEvjxqKP3W
        3DrtQi4Pqf2wvtBsjVoCrl7rD0VBVhkDWg80+RymeQneQlDP1Y9aF64nHBnv7nVm
        gZ2vI6oJgK3DcatvRnmt9ZbrUoPFcKpqfSLe3Gtswn6t6uaZbBWpkVB+4Pputocg
        FKkwjXZlEIFNROug7NIApZmmYatBM0DLmc3kZEkvp8VUG20+0/62WQ7lDw4/02Nk
        bOyKoVDa7K3DHydgQG3ntrqfMwlVEW+Wmw7G8qodH4fzhWJYXYGYbrTdVvTFUGs4
        zM+omk0t4azQf7UeJjMcf4anfn7qAHOJ1j13VIFF9EEmVOOe7CIUEHmwuvfml6B6
        rvBy4+gNANbnAJ61u8QZG5qVGT9YF/nlUIuoivm0TENdlwOv4Gw=
        =KDl+
        -----END PGP SIGNATURE-----
        
        --Apple-Mail=_18B291D9-548C-4458-8F17-B76537227FDF--
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body.strip() == "test 💩 é æ"
        assert parser.pgp_fingerprint == "86261D8DBEBDA4F54692D64DA8383BA780F238C6"

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_parse_invalid_signature_multipart_signed_ascii_bad_signature(self, tmp_gpg_dir, preload_gpg_key):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/signed;
         boundary="Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)


        --Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25
        Content-Transfer-Encoding: 7bit
        Content-Type: text/plain;
        \tcharset=us-ascii

        test 1 2 INVALID

        --Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25
        Content-Transfer-Encoding: 7bit
        Content-Disposition: attachment;
            filename=signature.asc
        Content-Type: application/pgp-signature;
            name=signature.asc
        Content-Description: Message signed with OpenPGP

        -----BEGIN PGP SIGNATURE-----

        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlthsw0ACgkQqDg7p4Dy
        OMbLdBAAnJ93CZYz6VNhHiSFhj2EtU6yG70chyAiCfrZXsXGWQXNBbkQBCpk3Cy0
        HD2cIBxh1612bDkct8ezWaS4uOEvp5gyEJg0/VrAMCvWIEXEFizE75kOgj3ay+hs
        Dj4C7TRlRvQdRbaNdCb3R27WMK9GPwDJgqjifZQu13pWkkAxQLpZBs+wbnWvh01X
        QWQdf7xr3PQUkm+uVE2fU7j+c1vQs5oJLMdvSuzSN59IvLiEmRFrkQF7yj3WCesh
        dTxAYl5TA8IhldXsc2/MYL24fNKk2L9Ns3Cr0x9XHYBk+w/iGQuCvTkTiOzeoxab
        puk83Xr+WDgVo6w6KT7n5ZFg7XRH/WV0hhdy6i+wuyXnwdTP5JQbJn66xZV4iYZh
        QAHrNeb/kRMcw7l6I3eL94W7ndfCZK7/XhHqYB4m88Jnbaklxih2gjJGWu50eQc7
        EXt0dl6BQeKlMtLWfgtBY4RzEglr1u99DSEqotJTlpSqUQ79rYwzKNvjI1Xc7yJc
        lLNwRJTtoWd8sUc0njlemxtVELNHUj0ahpQgMTqw1WbJu+FJxaTcRdbu6fYwl7hc
        k1Bt6Qyyn4qWD19aV6yClqyhJwZB2uoSKHvBmPIu31nHRYNr9SWD75dht8YODsmF
        QxtFWD7kfutDc40U0GjukbcPsfni1BH9AZZbUsm6YS7JMxoh1Rk=
        =92HM
        -----END PGP SIGNATURE-----
        """
        ).strip()
        parser = EmailParser(email)
        assert parser.body.strip() == "test 1 2 INVALID"
        assert parser.pgp_fingerprint is None

    def test_invalid_blank_body(self):
        email = textwrap.dedent(
            """
        From sasha@localhost  Thu Jan  5 10:04:48 2018
        Received: from [127.0.0.1] (localhost.localdomain [127.0.0.1])
          by hostname (Postfix) with ESMTPS id 740AD310597
          for <sasha@localhost>; Thu,  5 Jan 2018 10:04:48 +0100 (CET)
        Message-ID: <1325754288.4989.6.camel@hostname>
        Subject: my subject
        From: Sasha <sasha@example.com>
        To: sasha@localhost
        Date: Thu, 05 Jan 2018 10:04:48 +0100
        Content-Type: multipart/signed;
         boundary="Apple-Mail=_368A6867-FE85-4AFB-AACA-CDBA53C7DB25"
        Mime-Version: 1.0 (Mac OS X Mail 10.3 
        To: sasha@localhost
        X-Mailer: Apple Mail (2.3273)
        """
        ).strip()
        parser = EmailParser(email)
        assert not parser.body.strip()
        assert parser.pgp_fingerprint is None


class TestSendEmail:
    def test_send_email(self, monkeypatch):
        mock_smtp = Mock()
        monkeypatch.setattr("irrd.utils.email.SMTP", lambda server: mock_smtp)
        send_email("Sasha <sasha@example.com>", "subject", "body")
        assert mock_smtp.mock_calls[0][0] == "send_message"
        assert mock_smtp.mock_calls[0][1][0]["From"] == get_setting("email.from")
        assert mock_smtp.mock_calls[0][1][0]["To"] == "Sasha <sasha@example.com>"
        assert mock_smtp.mock_calls[0][1][0]["Subject"] == "subject"
        payload = mock_smtp.mock_calls[0][1][0].get_payload()
        assert "body" in payload
        assert "IRRd version" in payload
        assert get_setting("email.footer") in payload
        assert mock_smtp.mock_calls[1][0] == "quit"

    def test_send_email_with_recipient_override(self, monkeypatch, config_override):
        config_override({"email": {"recipient_override": "override@example.com"}})
        mock_smtp = Mock()
        monkeypatch.setattr("irrd.utils.email.SMTP", lambda server: mock_smtp)
        send_email("Sasha <sasha@example.com>", "subject", "body")
        assert mock_smtp.mock_calls[0][0] == "send_message"
        assert mock_smtp.mock_calls[0][1][0]["From"] == get_setting("email.from")
        assert mock_smtp.mock_calls[0][1][0]["To"] == "override@example.com"
        assert mock_smtp.mock_calls[0][1][0]["Subject"] == "subject"
