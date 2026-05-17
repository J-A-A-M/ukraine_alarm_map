const GITHUB_API_URL = 'https://api.github.com/repos/J-A-A-M/jaam_fusion/releases';
const NVS_API_URL = '/nvs/generate';
const NVS_OFFSET = 36864; // 0x9000

const BOARD_TYPES = {
    'ESP32': {
        appPattern: 'JAAM_',
        localFiles: {
            bootloader: 'bins/jaam.bootloader.bin',
            partitions: 'bins/jaam.partitions.bin',
            boot_app0: 'bins/jaam.boot.app0.bin'
        },
        offsets: { bootloader: 4096, partitions: 32768, boot_app0: 57344, app: 65536 }
    },
    'ESP32-S3': {
        appPattern: 'JAAM_s3_',
        localFiles: {
            bootloader: 'bins/jaam.bootloader.s3.bin',
            partitions: 'bins/jaam.partitions.s3.bin',
            boot_app0: 'bins/jaam.boot.app0.bin'
        },
        offsets: { bootloader: 0, partitions: 32768, boot_app0: 57344, app: 65536 }
    },
    'ESP32-C3': {
        appPattern: 'JAAM_c3_',
        localFiles: {
            bootloader: 'bins/jaam.bootloader.c3.bin',
            partitions: 'bins/jaam.partitions.c3.bin',
            boot_app0: 'bins/jaam.boot.app0.bin'
        },
        offsets: { bootloader: 0, partitions: 32768, boot_app0: 57344, app: 65536 }
    }
};

// Region list from jaam_fusion/src/JaamConfig.cpp DISTRICTS[]
// Only entries with ignore=false are included
const REGIONS = [
    {id: 9999, name: "АР Крим", oblast: true},

    {id: 4, name: "Вінницька обл.", oblast: true},
    {id: 36, name: "Вінницький район"},
    {id: 37, name: "Гайсинський район"},
    {id: 35, name: "Жмеринський район"},
    {id: 33, name: "Могилів-Подільський район"},
    {id: 32, name: "Тульчинський район"},
    {id: 34, name: "Хмільницький район"},

    {id: 8, name: "Волинська обл.", oblast: true},
    {id: 38, name: "Володимирський район"},
    {id: 41, name: "Камінь-Каширський район"},
    {id: 40, name: "Ковельський район"},
    {id: 39, name: "Луцький район"},

    {id: 9, name: "Дніпропетровська обл.", oblast: true},
    {id: 44, name: "Дніпровський район"},
    {id: 42, name: "Кам'янський район"},
    {id: 46, name: "Криворізький район"},
    {id: 47, name: "Нікопольський район"},
    {id: 43, name: "Самарівський район"},
    {id: 45, name: "Павлоградський район"},
    {id: 48, name: "Синельниківський район"},

    {id: 28, name: "Донецька обл.", oblast: true},
    {id: 54, name: "Бахмутський район"},
    {id: 55, name: "Волноваський район"},
    {id: 51, name: "Горлівський район"},
    {id: 53, name: "Донецький район"},
    {id: 49, name: "Кальміуський район"},
    {id: 50, name: "Краматорський район"},
    {id: 52, name: "Маріупольський район"},
    {id: 56, name: "Покровський район"},

    {id: 10, name: "Житомирська обл.", oblast: true},
    {id: 57, name: "Бердичівський район"},
    {id: 59, name: "Житомирський район"},
    {id: 60, name: "Звягельський район"},
    {id: 58, name: "Коростенський район"},

    {id: 11, name: "Закарпатська обл.", oblast: true},
    {id: 61, name: "Берегівський район"},
    {id: 62, name: "Хустський район"},
    {id: 65, name: "Мукачівський район"},
    {id: 63, name: "Рахівський район"},
    {id: 64, name: "Тячівський район"},
    {id: 66, name: "Ужгородський район"},

    {id: 12, name: "Запорізька обл.", oblast: true},
    {id: 146, name: "Василівський район"},
    {id: 147, name: "Бердянський район"},
    {id: 149, name: "Запорізький район"},
    {id: 148, name: "Мелітопольський район"},
    {id: 145, name: "Пологівський район"},
    {id: 564, name: "м. Запоріжжя"},

    {id: 13, name: "Ів.-Франківська обл.", oblast: true},
    {id: 67, name: "Верховинський район"},
    {id: 68, name: "Івано-Франківський район"},
    {id: 71, name: "Калуський район"},
    {id: 70, name: "Коломийський район"},
    {id: 69, name: "Косівський район"},
    {id: 72, name: "Надвірнянський район"},

    {id: 31, name: "м. Київ", oblast: true},

    {id: 14, name: "Київська обл.", oblast: true},
    {id: 73, name: "Білоцерківський район"},
    {id: 78, name: "Бориспільський район"},
    {id: 79, name: "Броварський район"},
    {id: 75, name: "Бучанський район"},
    {id: 74, name: "Вишгородський район"},
    {id: 76, name: "Обухівський район"},
    {id: 77, name: "Фастівський район"},

    {id: 15, name: "Кіровоградська обл.", oblast: true},
    {id: 82, name: "Голованівський район"},
    {id: 81, name: "Кропивницький район"},
    {id: 83, name: "Новоукраїнський район"},
    {id: 80, name: "Олександрійський район"},

    {id: 16, name: "Луганська обл.", oblast: true},

    {id: 27, name: "Львівська обл.", oblast: true},
    {id: 91, name: "Дрогобицький район"},
    {id: 94, name: "Золочівський район"},
    {id: 90, name: "Львівський район"},
    {id: 88, name: "Самбірський район"},
    {id: 89, name: "Стрийський район"},
    {id: 92, name: "Шептицький район"},
    {id: 93, name: "Яворівський район"},

    {id: 17, name: "Миколаївська обл.", oblast: true},
    {id: 96, name: "Баштанський район"},
    {id: 95, name: "Вознесенський район"},
    {id: 98, name: "Миколаївський район"},
    {id: 97, name: "Первомайський район"},

    {id: 18, name: "Одеська обл.", oblast: true},
    {id: 100, name: "Березівський район"},
    {id: 102, name: "Білгород-Дністровський район"},
    {id: 105, name: "Болградський район"},
    {id: 101, name: "Ізмаїльський район"},
    {id: 104, name: "Одеський район"},
    {id: 99, name: "Подільський район"},
    {id: 103, name: "Роздільнянський район"},

    {id: 19, name: "Полтавська обл.", oblast: true},
    {id: 107, name: "Кременчуцький район"},
    {id: 106, name: "Лубенський район"},
    {id: 108, name: "Миргородський район"},
    {id: 109, name: "Полтавський район"},

    {id: 5, name: "Рівненська обл.", oblast: true},
    {id: 110, name: "Вараський район"},
    {id: 111, name: "Дубенський район"},
    {id: 112, name: "Рівненський район"},
    {id: 113, name: "Сарненський район"},

    {id: 20, name: "Сумська обл.", oblast: true},
    {id: 117, name: "Конотопський район"},
    {id: 118, name: "Охтирський район"},
    {id: 116, name: "Роменський район"},
    {id: 114, name: "Сумський район"},
    {id: 115, name: "Шосткинський район"},

    {id: 21, name: "Тернопільська обл.", oblast: true},
    {id: 120, name: "Кременецький район"},
    {id: 119, name: "Тернопільський район"},
    {id: 121, name: "Чортківський район"},

    {id: 22, name: "Харківська обл.", oblast: true},
    {id: 126, name: "Богодухівський район"},
    {id: 125, name: "Ізюмський район"},
    {id: 127, name: "Берестинський район"},
    {id: 123, name: "Куп'янський район"},
    {id: 128, name: "Лозівський район"},
    {id: 124, name: "Харківський район"},
    {id: 122, name: "Чугуївський район"},
    {id: 1293, name: "м. Харків"},

    {id: 23, name: "Херсонська обл.", oblast: true},
    {id: 129, name: "Бериславський район"},
    {id: 133, name: "Генічеський район"},
    {id: 131, name: "Каховський район"},
    {id: 130, name: "Скадовський район"},
    {id: 132, name: "Херсонський район"},

    {id: 3, name: "Хмельницька обл.", oblast: true},
    {id: 135, name: "Кам'янець-Подільський район"},
    {id: 134, name: "Хмельницький район"},
    {id: 136, name: "Шепетівський район"},

    {id: 24, name: "Черкаська обл.", oblast: true},
    {id: 150, name: "Звенигородський район"},
    {id: 153, name: "Золотоніський район"},
    {id: 151, name: "Уманський район"},
    {id: 152, name: "Черкаський район"},

    {id: 26, name: "Чернівецька обл.", oblast: true},
    {id: 138, name: "Вижницький район"},
    {id: 139, name: "Дністровський район"},
    {id: 137, name: "Чернівецький район"},

    {id: 25, name: "Чернігівська обл.", oblast: true},
    {id: 144, name: "Корюківський район"},
    {id: 142, name: "Ніжинський район"},
    {id: 141, name: "Новгород-Сіверський район"},
    {id: 143, name: "Прилуцький район"},
    {id: 140, name: "Чернігівський район"},
];

// JAAM hardware presets that hide hardware section
const JAAM_LEGACY_PRESETS = new Set(['0', '3', '4', '6', '9']);

// Firmware 5.1+ uses wifi_nets namespace; older versions use WiFiManager "wm" namespace
function useLegacyWifi(release) {
    const match = release.tag_name.replace(/^v/i, '').match(/^(\d+)\.(\d+)/);
    if (!match) return true;
    const [, major, minor] = match.map(Number);
    return major < 5 || (major === 5 && minor < 1);
}

let releases = [];
let selectedRelease = null;
let nvsObjectUrl = null;
let flashReady = false;

// Populate region select
function populateRegionSelect() {
    const select = document.getElementById('cfg-region');
    REGIONS.forEach(r => {
        const option = document.createElement('option');
        option.value = r.id;
        option.textContent = r.oblast ? r.name : '  — ' + r.name;
        if (r.oblast) option.style.fontWeight = 'bold';
        select.appendChild(option);
    });
}

// Get current config form data (only filled fields)
function getConfigData() {
    const ssid = document.getElementById('cfg-ssid').value.trim();
    const password = document.getElementById('cfg-password').value;
    const region = document.getElementById('cfg-region').value;
    const deviceName = document.getElementById('cfg-device-name').value.trim();
    const legacy = document.getElementById('cfg-legacy').value;
    const fwuc = document.querySelector('input[name="cfg-fwuc"]:checked')?.value;
    const ledPin = document.getElementById('cfg-led-pin').value.trim();
    const ledCount = document.getElementById('cfg-led-count').value.trim();
    const bgLedPin = document.getElementById('cfg-bg-led-pin').value.trim();
    const bgLedCount = document.getElementById('cfg-bg-led-count').value.trim();
    const serviceLedPin = document.getElementById('cfg-service-led-pin').value.trim();
    const display = document.getElementById('cfg-display').value;
    const displaySize = document.getElementById('cfg-display-size').value;
    const sound = document.getElementById('cfg-sound').value;
    const buzzerPin = document.getElementById('cfg-buzzer-pin').value.trim();

    const data = {};
    if (ssid) { data.ssid = ssid; data.password = password; data.wifi_legacy = useLegacyWifi(selectedRelease); }
    if (region) data.home_district = parseInt(region);
    if (deviceName) data.device_name = deviceName;
    if (legacy !== '') data.legacy = parseInt(legacy);
    if (fwuc !== undefined) data.fw_update_channel = parseInt(fwuc);
    if (ledPin !== '') data.led_pin = parseInt(ledPin);
    if (ledCount !== '') data.led_count = parseInt(ledCount);
    if (bgLedPin !== '') data.bg_led_pin = parseInt(bgLedPin);
    if (bgLedCount !== '') data.bg_led_count = parseInt(bgLedCount);
    if (serviceLedPin !== '') data.service_led_pin = parseInt(serviceLedPin);
    if (display !== '') {
        data.display_model = parseInt(display);
        if (parseInt(display) > 0) {
            data.display_width = 128;
            data.display_height = parseInt(displaySize);
        }
    }
    if (sound !== '') data.sound_source = parseInt(sound);
    if (buzzerPin !== '') data.buzzer_pin = parseInt(buzzerPin);

    return Object.keys(data).length > 0 ? data : null;
}

// Fetch NVS binary from API and return blob URL (or null if no config)
async function fetchNVS() {
    const configData = getConfigData();
    if (!configData) return null;

    setConfigStatus('Підготовка конфігурації...', false);
    try {
        const response = await fetch(NVS_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(configData),
        });
        if (!response.ok) {
            const err = await response.text();
            throw new Error(err);
        }
        const buf = await response.arrayBuffer();
        if (nvsObjectUrl) URL.revokeObjectURL(nvsObjectUrl);
        nvsObjectUrl = URL.createObjectURL(new Blob([buf]));
        setConfigStatus('Прошивка готова ✓', false);
        return nvsObjectUrl;
    } catch (e) {
        setConfigStatus('Помилка конфігурації: ' + e.message, true);
        return null;
    }
}

function setConfigStatus(text, isError) {
    const el = document.getElementById('cfg-status');
    if (!el) return;
    el.textContent = text;
    el.style.color = isError ? '#dc3545' : '#28a745';
}

// Build and set manifest on the install button
async function generateAndSetManifest() {
    if (!selectedRelease) return;

    const manifest = {
        name: selectedRelease.prerelease ? "JAAM Beta" : "JAAM",
        version: selectedRelease.tag_name,
        funding_url: "https://send.monobank.ua/jar/7GzS1PhPa2",
        new_install_improv_wait_time: 0,
        new_install_prompt_erase: true,
        builds: []
    };

    const baseUrl = window.location.href.substring(0, window.location.href.lastIndexOf('/') + 1);
    const nvsUrl = await fetchNVS();

    for (const [boardType, config] of Object.entries(BOARD_TYPES)) {
        const build = { chipFamily: boardType, improv: false, parts: [] };

        build.parts.push({ path: baseUrl + config.localFiles.bootloader, offset: config.offsets.bootloader });
        build.parts.push({ path: baseUrl + config.localFiles.partitions, offset: config.offsets.partitions });

        if (nvsUrl) {
            build.parts.push({ path: nvsUrl, offset: NVS_OFFSET });
        }

        build.parts.push({ path: baseUrl + config.localFiles.boot_app0, offset: config.offsets.boot_app0 });

        let appUrl;
        if (boardType === 'ESP32') {
            appUrl = `https://update.jaam.net.ua/${selectedRelease.tag_name}`;
        } else if (boardType === 'ESP32-C3') {
            appUrl = `https://update.jaam.net.ua/c3/${selectedRelease.tag_name}`;
        } else if (boardType === 'ESP32-S3') {
            appUrl = `https://update.jaam.net.ua/s3/${selectedRelease.tag_name}`;
        }
        build.parts.push({ path: appUrl, offset: config.offsets.app });

        manifest.builds.push(build);
    }

    const manifestUrl = `data:application/json;base64,${btoa(JSON.stringify(manifest))}`;
    document.getElementById('stable-install-btn').setAttribute('manifest', manifestUrl);
}

// Reset to prepare stage when config changes after preparation
function onConfigChange() {
    if (flashReady) resetToPrepare();
}

// Prepare: generate NVS (if config) and transition to flash button
async function prepareFlash() {
    const btn = document.getElementById('prepare-btn');
    btn.disabled = true;
    btn.textContent = 'Підготовка...';

    await generateAndSetManifest();

    btn.disabled = false;
    btn.textContent = 'Підготувати прошивку';
    flashReady = true;
    document.getElementById('prepare-section').style.display = 'none';
    document.getElementById('install-buttons').style.display = 'block';
}
window.prepareFlash = prepareFlash;

function resetToPrepare() {
    flashReady = false;
    document.getElementById('install-buttons').style.display = 'none';
    document.getElementById('prepare-section').style.display = 'block';
    setConfigStatus('', false);
}

function togglePasswordVisibility() {
    const input = document.getElementById('cfg-password');
    const eyeIcon = document.getElementById('eye-icon');
    const eyeOffIcon = document.getElementById('eye-off-icon');
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    eyeIcon.style.display = isHidden ? 'none' : '';
    eyeOffIcon.style.display = isHidden ? '' : 'none';
}

function resetConfig() {
    document.getElementById('cfg-ssid').value = '';
    document.getElementById('cfg-password').value = '';
    document.getElementById('cfg-region').value = '';
    document.getElementById('cfg-device-name').value = '';
    document.getElementById('cfg-legacy').value = '';
    document.querySelectorAll('input[name="cfg-fwuc"]')[0].checked = true;
    document.getElementById('cfg-led-pin').value = '';
    document.getElementById('cfg-led-count').value = '';
    document.getElementById('cfg-bg-led-pin').value = '';
    document.getElementById('cfg-bg-led-count').value = '';
    document.getElementById('cfg-service-led-pin').value = '';
    document.getElementById('cfg-display').value = '';
    document.getElementById('cfg-display-size').value = '32';
    document.getElementById('cfg-sound').value = '';
    document.getElementById('cfg-buzzer-pin').value = '';
    document.getElementById('cfg-hardware-section').style.display = 'none';
    document.getElementById('cfg-led-count-group').style.display = 'none';
    document.getElementById('cfg-display-size-group').style.display = 'none';
    document.getElementById('cfg-buzzer-pin-group').style.display = 'none';
    document.getElementById('cfg-password').type = 'password';
    document.getElementById('eye-icon').style.display = '';
    document.getElementById('eye-off-icon').style.display = 'none';
    setConfigStatus('', false);
    if (nvsObjectUrl) { URL.revokeObjectURL(nvsObjectUrl); nvsObjectUrl = null; }
    if (flashReady) resetToPrepare();
}
window.resetConfig = resetConfig;

// Fetch releases from GitHub
async function fetchReleases() {
    try {
        const response = await fetch(GITHUB_API_URL, {
            headers: { 'Accept': 'application/vnd.github.v3+json' }
        });

        if (!response.ok) throw new Error('Failed to fetch releases');

        const allReleases = await response.json();

        const stable = allReleases.filter(r => !r.prerelease && !r.draft);
        const preReleases = allReleases.filter(r => r.prerelease && !r.draft);

        const latestStable = stable.slice(0, 7);
        const latestPreReleases = preReleases.slice(0, 7);

        releases = [...latestStable, ...latestPreReleases].sort(
            (a, b) => new Date(b.published_at) - new Date(a.published_at)
        );

        populateReleaseSelect();

        if (stable.length > 0) {
            const latestStableIndex = releases.findIndex(r => r.id === stable[0].id);
            if (latestStableIndex !== -1) {
                const select = document.getElementById('release-select');
                select.value = latestStableIndex;
                select.dispatchEvent(new Event('change'));
            }
        }
    } catch (error) {
        document.getElementById('release-select').innerHTML =
            '<option value="">Помилка при завантаженні релізів</option>';
    }
}

function populateReleaseSelect() {
    const select = document.getElementById('release-select');
    select.innerHTML = '';
    releases.forEach((release, index) => {
        const option = document.createElement('option');
        const label = release.prerelease ? ` [Beta]` : '';
        option.value = index;
        option.textContent = `${release.tag_name}${label}`;
        select.appendChild(option);
    });
}

function showFlashButton() {
    document.getElementById('install-buttons').style.display = 'block';
    document.getElementById('prepare-section').style.display = 'none';
}

function showPrepareButton() {
    document.getElementById('install-buttons').style.display = 'none';
    document.getElementById('prepare-section').style.display = 'block';
    flashReady = false;
}

document.getElementById('release-select').addEventListener('change', async function() {
    const selectedIndex = this.value;

    if (selectedIndex === '') {
        document.getElementById('config-details').style.display = 'none';
        document.getElementById('prepare-section').style.display = 'none';
        document.getElementById('install-buttons').style.display = 'none';
        document.getElementById('release-notes-section').style.display = 'none';
        flashReady = false;
        return;
    }

    selectedRelease = releases[selectedIndex];
    flashReady = false;

    const tagName = selectedRelease.tag_name;
    const preLabel = selectedRelease.prerelease ? ' (Beta)' : '';
    document.getElementById('stable-btn-text').textContent = `Встановити JAAM ${tagName}${preLabel}`;
    document.getElementById('config-details').style.display = '';
    setConfigStatus('', false);

    const details = document.getElementById('config-details');
    if (details.open) {
        showPrepareButton();
    } else {
        await generateAndSetManifest();
        showFlashButton();
    }

    displayReleaseNotes(selectedRelease);
});

document.getElementById('config-details').addEventListener('toggle', async function() {
    if (!selectedRelease) return;
    if (this.open) {
        setConfigStatus('', false);
        showPrepareButton();
    } else {
        if (nvsObjectUrl) { URL.revokeObjectURL(nvsObjectUrl); nvsObjectUrl = null; }
        setConfigStatus('', false);
        await generateAndSetManifest();
        showFlashButton();
    }
});

// Config form event listeners (wired after DOM ready)
function wireConfigListeners() {
    const fields = ['cfg-ssid', 'cfg-password', 'cfg-region', 'cfg-device-name', 'cfg-legacy', 'cfg-led-pin', 'cfg-led-count', 'cfg-bg-led-pin', 'cfg-bg-led-count', 'cfg-service-led-pin', 'cfg-display', 'cfg-display-size', 'cfg-sound', 'cfg-buzzer-pin'];
    fields.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', onConfigChange);
        if (el && el.tagName === 'INPUT') el.addEventListener('input', onConfigChange);
    });
    document.querySelectorAll('input[name="cfg-fwuc"]').forEach(el => el.addEventListener('change', onConfigChange));

    // Legacy select: hide hardware section for JAAM presets; hide LED count for map presets
    document.getElementById('cfg-legacy').addEventListener('change', function() {
        const hw = document.getElementById('cfg-hardware-section');
        const ledCountGroup = document.getElementById('cfg-led-count-group');
        if (this.value === '' || JAAM_LEGACY_PRESETS.has(this.value)) {
            hw.style.display = 'none';
        } else {
            hw.style.display = '';
            ledCountGroup.style.display = this.value === '5' ? '' : 'none';
        }
    });

    // Display model: show size selector when model != none
    document.getElementById('cfg-display').addEventListener('change', function() {
        const sizeGroup = document.getElementById('cfg-display-size-group');
        sizeGroup.style.display = (this.value !== '' && this.value !== '0') ? '' : 'none';
    });

    // Sound source: show buzzer pin when buzzer selected
    document.getElementById('cfg-sound').addEventListener('change', function() {
        const pinGroup = document.getElementById('cfg-buzzer-pin-group');
        pinGroup.style.display = (this.value === '0') ? '' : 'none';
    });
}

// Simple markdown to HTML converter for GitHub-style markdown
function markdownToHtml(markdown) {
    if (!markdown) return '';

    let html = markdown;

    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');

    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/_(.+?)_/g, '<em>$1</em>');

    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    html = html.replace(/^> (.*?)$/gm, '<blockquote>$1</blockquote>');
    html = html.replace(/<\/blockquote>\n<blockquote>/g, '\n');

    html = html.replace(/^\* (.*?)$/gm, '<li>$1</li>');
    html = html.replace(/^\- (.*?)$/gm, '<li>$1</li>');
    html = html.replace(/^  \* (.*?)$/gm, '<li style="margin-left: 20px;">$1</li>');
    html = html.replace(/^  \- (.*?)$/gm, '<li style="margin-left: 20px;">$1</li>');
    html = html.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');
    html = html.replace(/<\/li>\s*<ul>/g, '<ul>');
    html = html.replace(/<\/ul>\s*<li>/g, '<li>');

    const lines = html.split('\n');
    let result = '';
    let inBlock = false;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.match(/^<(h|ul|pre|ol)/)) {
            result += line;
            inBlock = true;
        } else if (line.match(/^<\/(h|ul|pre|ol)/)) {
            result += line;
            inBlock = false;
        } else if (line.trim() === '') {
            if (!inBlock) result += '<br>';
        } else if (line.match(/^<li>/)) {
            result += line;
        } else if (!inBlock && line.trim()) {
            result += '<p>' + line + '</p>';
        } else {
            result += line;
        }
    }

    return result;
}

function displayReleaseNotes(release) {
    const notesSection = document.getElementById('release-notes-section');
    const notesContent = document.getElementById('release-notes-content');

    if (release.body) {
        notesContent.innerHTML = markdownToHtml(release.body);
        notesSection.style.display = 'block';
    } else {
        notesContent.innerHTML = '<p>Опис версії недоступний</p>';
        notesSection.style.display = 'block';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    initTheme();
    populateRegionSelect();
    wireConfigListeners();
    fetchReleases();
});

// Theme helpers
function detectSystemTheme() {
    return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
}

function getThemeFromCookie() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'jaam_theme') return value;
    }
    return null;
}

function setThemeCookie(theme) {
    document.cookie = 'jaam_theme=' + theme + '; max-age=31536000; path=/';
}

function applyTheme(theme, persist = true) {
    document.documentElement.setAttribute('data-theme', theme);
    if (persist) setThemeCookie(theme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark', true);
}
window.toggleTheme = toggleTheme;

function initTheme() {
    const savedTheme = getThemeFromCookie();
    const theme = savedTheme || detectSystemTheme();
    applyTheme(theme, !!savedTheme);
    if (!savedTheme && window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addListener(function(e) {
            if (!getThemeFromCookie()) applyTheme(e.matches ? 'dark' : 'light', false);
        });
    }
}
