from passlib.hash import des_crypt, md5_crypt, bcrypt

PASSWORD_HASHERS = {
    'CRYPT-PW': des_crypt,
    'MD5-PW': md5_crypt,
    'BCRYPT-PW': bcrypt,
}
