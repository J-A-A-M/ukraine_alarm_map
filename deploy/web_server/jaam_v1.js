const urlParams = new URLSearchParams(window.location.search);
const activePage = urlParams.get('p');
var target = '';
switch (activePage) {
    case 'brgh':
        target = 'clB';
        break;
    case 'clrs':
        target = 'clC';
        break;
    case 'mds':
        target = 'clM';
        break;
    case 'snd':
        target = 'clS';
        break;
    case 'tlmtr':
        target = 'clT';
        break;
    case 'tch':
        target = 'cTc';
        break;
    case 'fw':
        target = 'clF';
        break;
}

if (target.length > 0) {
    document.getElementById(target).classList.add('show');
    window.scrollTo(0, document.body.scrollHeight);
}

if (urlParams.get('svd') === '1') {
    const toast = document.getElementById('liveToast');
    toast.classList.remove('hide');
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
        toast.classList.add('hide');
    }, 2000);
}

/**
 * Sends an asynchronous request to play a test sound with the specified ID.
 *
 * @param {number} [soundId=4] - The ID of the sound to play.
 */
function playTestSound(soundId = 4) {
    var xhttp = new XMLHttpRequest();
    xhttp.open('GET', '/playTestSound/?id='.concat(soundId), true);
    xhttp.send();
}

/**
 * Sends an asynchronous request to play a test track with the specified sound ID.
 *
 * @param {number} [soundId=1] - The ID of the track to play.
 */
function playTestTrack(soundId = 1) {
    var xhttp = new XMLHttpRequest();
    xhttp.open('GET', '/playTestTrackById/?id='.concat(soundId), true);
    xhttp.send();
}


/**
 * Enables or disables all elements with the specified name attribute.
 *
 * @param {string} targetName - The value of the name attribute for target elements.
 * @param {boolean} disable - If true, disables the elements; if false, enables them.
 */
function disableElement(targetName, disable) {
    document.getElementsByName(targetName).forEach((elem) => {
        elem.disabled = disable;
    });
}

function updateColAndVal(colorId, valueId, value) {
    updateColorBox(colorId, value);
    updateVal(valueId, value);
}

function updateVal(valueId, value) {
    document.getElementById(valueId).textContent = value;
}

function updateColorBox(boxId, hue) {
    const rgbColor = hsbToRgb(hue, 100, 100);
    document.getElementById(boxId).style.backgroundColor = `rgb(${rgbColor.r}, ${rgbColor.g}, ${rgbColor.b})`;
}

function hsbToRgb(h, s, b) {
    h /= 360;
    s /= 100;
    b /= 100;

    let r, g, bl;

    if (s === 0) {
        r = g = bl = b;
    } else {
        const i = Math.floor(h * 6);
        const f = h * 6 - i;
        const p = b * (1 - s);
        const q = b * (1 - f * s);
        const t = b * (1 - (1 - f) * s);

        switch (i % 6) {
            case 0: r = b, g = t, bl = p; break;
            case 1: r = q, g = b, bl = p; break;
            case 2: r = p, g = b, bl = t; break;
            case 3: r = p, g = q, bl = b; break;
            case 4: r = t, g = p, bl = b; break;
            case 5: r = b, g = p, bl = q; break;
        }
    }

    return {
        r: Math.round(r * 255),
        g: Math.round(g * 255),
        b: Math.round(bl * 255)
    };
}

$('select[name=brightness_auto]').change(function () {
    const selectedOption = $(this).val();
    $('input[name=brightness]').prop('disabled', selectedOption == 1 || selectedOption == 2);
    $('input[name=brightness_day]').prop('disabled', selectedOption == 0);
    $('input[name=day_start]').prop('disabled', selectedOption == 0 || selectedOption == 2);
    $('input[name=night_start]').prop('disabled', selectedOption == 0 || selectedOption == 2);
});

$('select[name=alarms_notify_mode]').change(function () {
    const selectedOption = $(this).val();
    $('input[name=alert_on_time]').prop('disabled', selectedOption == 0);
    $('input[name=alert_off_time]').prop('disabled', selectedOption == 0);
    $('input[name=explosion_time]').prop('disabled', selectedOption == 0);
    $('input[name=alert_blink_time]').prop('disabled', selectedOption != 2);
});
