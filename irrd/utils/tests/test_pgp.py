# flake8: noqa: W293

import textwrap

import pytest

from ..pgp import validate_pgp_signature


class TestValidatePGPSignature:
    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_valid_detached_signed_ascii(self, tmp_gpg_dir, preload_gpg_key):
        message = (
            textwrap.dedent(
                """
        Content-Transfer-Encoding: 7bit
        Content-Type: text/plain;
        \tcharset=us-ascii

        test 1 2 3
        """
            ).strip()
            + "\n"
        )

        signature = textwrap.dedent(
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
        -----END PGP SIGNATURE-----
        """
        ).strip()
        new_message, fingerprint = validate_pgp_signature(message, signature)
        assert new_message is None
        assert fingerprint == "86261D8DBEBDA4F54692D64DA8383BA780F238C6"

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_valid_inline_signed_ascii(self, tmp_gpg_dir, preload_gpg_key):
        message = textwrap.dedent(
            """
        UNSIGNED TEXT TO BE IGNORED

        -----BEGIN PGP SIGNED MESSAGE-----
        Hash: SHA256
        
        test
        1
        
        2
        
        3
        
        -----BEGIN PGP SIGNATURE-----
        
        iQIzBAEBCAAdFiEEhiYdjb69pPVGktZNqDg7p4DyOMYFAlw3Jb8ACgkQqDg7p4Dy
        OMZEmA//RSVSModFylC660mlqkQ5kzWJEWMxJJ5hlIHHYmWjanW2XG+KxyKr/EFK
        xgZRzdj8p7UuuVPH5Zw6YkNMBefe3mqZC/I/QKPzkvZlWy/j4jQPqL5ogTZMtjpn
        Obb6p8rVyqyz7jS68h4zpAxp9TjciQHdBHGhMxTCIPKEHLDdW5SkFS8gXBvYqmOq
        VicJgnC1ZY5UuPnXN7EzSL+mR7CCjLSbOCPGsoJi1dh0UXOIuEu/8t+M4V8iFkj2
        4Ir6AIy1DTRNhUVspSS2ADYIyox1Gzg4Lr8JXQwDHD8fsLYerq6/a2fbGoAU9MAO
        epzoAqnpDUyiEF7BuIYwHc03RhgonfT6KPTIlKph2AFifPN+h9NNi7Sr0jPvEkyQ
        6OXFeFpHEHfrJv2m3Hbf9++xxawUXGeJ/gFTNJXwQeaTvoEyhU9uwwEzibFww77V
        GGqBgzVjHX2RTc24e9OrKSoN8dOs3jsVj0Ucnxuh2nX0y/RaBOM95hUwhokgxGoQ
        XZzQn3mPAPE3sZ05YyYIa1eWYxwwwI1xDxW/sC8VMYCDl1sc1w+g7riOm2eam6eg
        YBfZyLf62EwyIj+y9TGAyfGe41cDtNzcNB2wUdoW3TEN8u3jS/euvtjFOIQ6aofs
        JWTW+eqHBNWWC7Rfi1B7Pqh1bkk1FWPaxCJij73ekV8ZNiBBmwA=
        =iWS2
        -----END PGP SIGNATURE-----

        """
        ).strip()
        new_message, fingerprint = validate_pgp_signature(message)
        assert new_message.strip() == "test\n1\n\n2\n\n3"
        assert fingerprint == "86261D8DBEBDA4F54692D64DA8383BA780F238C6"

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_invalid_inline_signed_ascii_multiple_messages(self, tmp_gpg_dir, preload_gpg_key):
        message = textwrap.dedent(
            """
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
        new_message, fingerprint = validate_pgp_signature(message)
        assert new_message is None
        assert fingerprint is None

    @pytest.mark.usefixtures("tmp_gpg_dir")
    def test_invalid_signature_detached_signed_ascii(self, tmp_gpg_dir, preload_gpg_key):
        message = (
            textwrap.dedent(
                """
        Content-Transfer-Encoding: 7bit
        Content-Type: text/plain;
        \tcharset=us-ascii

        test 1 2 INVALID
        """
            ).strip()
            + "\n"
        )
        signature = textwrap.dedent(
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
        -----END PGP SIGNATURE-----
        """
        ).strip()
        new_message, fingerprint = validate_pgp_signature(message, signature)
        assert new_message is None
        assert fingerprint is None
