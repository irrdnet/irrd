var dataEl = document.getElementById('webauthn-register-data');
var opts = JSON.parse(dataEl.dataset.options);
var verifyUrl = dataEl.dataset.verifyUrl;
var successUrl = dataEl.dataset.successUrl;
var errorBox = document.getElementById('error-box');

document.getElementById('webauthn-register').addEventListener('click', async function () {
    errorBox.classList.add('d-none');
    var regResp;
    try {
        regResp = await SimpleWebAuthnBrowser.startRegistration(opts);
    } catch (err) {
        errorBox.classList.remove('d-none');
        return;
    }
    var registrationResp = await fetch(verifyUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            'name': document.getElementById('name').value,
            'registration_response': JSON.stringify(regResp),
        }),
    });
    var registrationResult = await registrationResp.json();
    if (registrationResult.success) {
        window.location.href = successUrl;
    } else {
        errorBox.classList.remove('d-none');
    }
});
