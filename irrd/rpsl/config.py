from passlib.hash import des_crypt, md5_crypt

PASSWORD_HASHERS = {
    'CRYPT-PW': des_crypt,
    'MD5-PW': md5_crypt,
}
