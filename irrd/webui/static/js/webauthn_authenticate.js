var dataEl = document.getElementById('webauthn-authenticate-data');
var opts = JSON.parse(dataEl.dataset.options);
var next = dataEl.dataset.next;
var verifyUrl = dataEl.dataset.verifyUrl;
var errorBox = document.getElementById('error-box');

document.getElementById('webauthn-authenticate').addEventListener('click', async function () {
    errorBox.classList.add('d-none');
    var asseResp;
    try {
        asseResp = await SimpleWebAuthnBrowser.startAuthentication(opts);
    } catch (err) {
        errorBox.classList.remove('d-none');
        return;
    }
    var verificationResp = await fetch(verifyUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(asseResp),
    });
    var verificationResult = await verificationResp.json();
    if (verificationResult.verified) {
        window.location.href = next;
    } else {
        errorBox.classList.remove('d-none');
    }
});
