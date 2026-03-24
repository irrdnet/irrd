var canvas = document.getElementById('canvas');
QRCode.toCanvas(canvas, canvas.dataset.totpUrl, function (error) {
    if (error) console.error(error);
});
