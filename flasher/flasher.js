const GITHUB_API_URL = 'https://api.github.com/repos/J-A-A-M/jaam_fusion/releases';
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

let releases = [];
let selectedRelease = null;

// Fetch releases from GitHub
async function fetchReleases() {
    try {
        const response = await fetch(GITHUB_API_URL, {
            headers: {
                'Accept': 'application/vnd.github.v3+json'
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch releases');
        }

        const allReleases = await response.json();
        
        // Separate into stable and pre-releases
        const stable = allReleases.filter(r => !r.prerelease && !r.draft);
        const preReleases = allReleases.filter(r => r.prerelease && !r.draft);
        
        // Take last 5 of each type
        const latestStable = stable.slice(0, 5);
        const latestPreReleases = preReleases.slice(0, 5);
        
        // Combine and sort by published date (newest first)
        releases = [...latestStable, ...latestPreReleases].sort(
            (a, b) => new Date(b.published_at) - new Date(a.published_at)
        );
        
        populateReleaseSelect();
        
        // Auto-select the latest stable release
        if (stable.length > 0) {
            const latestStableIndex = releases.findIndex(r => r.id === stable[0].id);
            if (latestStableIndex !== -1) {
                const select = document.getElementById('release-select');
                select.value = latestStableIndex;
                // Trigger change event to load the selected release
                select.dispatchEvent(new Event('change'));
            }
        }
    } catch (error) {
        console.error('Error fetching releases:', error);
        document.getElementById('release-select').innerHTML = 
            '<option value="">Помилка при завантаженні релізів</option>';
    }
}

// Populate the select element with releases
function populateReleaseSelect() {
    const select = document.getElementById('release-select');
    select.innerHTML = '<option value="">Виберіть версію...</option>';
    
    releases.forEach((release, index) => {
        const option = document.createElement('option');
        const label = release.prerelease ? ` [Beta]` : '';
        option.value = index;
        option.textContent = `${release.tag_name}${label}`;
        select.appendChild(option);
    });
}

// Generate manifest from release
function generateManifest(release, variantType) {
    const manifest = {
        name: `JAAM ${release.tag_name}${variantType ? ' ' + variantType : ''}`,
        version: release.tag_name,
        funding_url: "https://send.monobank.ua/jar/7GzS1PhPa2",
        new_install_improv_wait_time: 0,
        new_install_prompt_erase: true,
        builds: []
    };

    console.log('Release assets:', release.assets.map(a => a.name));

    // Build configurations for each board type
    Object.entries(BOARD_TYPES).forEach(([boardType, config]) => {
        const buildConfig = {
            chipFamily: boardType,
            improv: false,
            parts: []
        };

        // Add local files for bootloader, partitions, and boot.app0
        buildConfig.parts.push({
            path: config.localFiles.bootloader,
            offset: config.offsets.bootloader
        });
        buildConfig.parts.push({
            path: config.localFiles.partitions,
            offset: config.offsets.partitions
        });
        buildConfig.parts.push({
            path: config.localFiles.boot_app0,
            offset: config.offsets.boot_app0
        });

        // Find app binary from GitHub assets
        console.log(`Looking for ${boardType} app binary with pattern: ${config.appPattern}`);
        
        const foundAsset = release.assets.find(asset => 
            asset.name.toLowerCase().includes(config.appPattern.toLowerCase()) && asset.name.endsWith('.bin')
        );
        
        console.log(`${boardType} app binary - Found:`, foundAsset ? foundAsset.name : 'NOT FOUND');
        
        if (foundAsset) {
            buildConfig.parts.push({
                path: foundAsset.browser_download_url,
                offset: config.offsets.app
            });
            manifest.builds.push(buildConfig);
        } else {
            console.warn(`${boardType} - Missing app binary with pattern "${config.appPattern}"`);
        }
    });

    return manifest;
}

// Handle release selection
document.getElementById('release-select').addEventListener('change', async function(e) {
    const selectedIndex = this.value;
    
    if (selectedIndex === '') {
        document.getElementById('install-buttons').style.display = 'none';
        document.getElementById('release-notes-section').style.display = 'none';
        return;
    }

    selectedRelease = releases[selectedIndex];
    
    // Generate and set manifest
    const stableManifest = generateManifest(selectedRelease, 'stable');

    // Log manifest to console
    console.log('Generated Manifest:', stableManifest);

    // Convert manifest to data URL
    const stableUrl = `data:application/json;base64,${btoa(JSON.stringify(stableManifest))}`;

    // Update install button
    document.getElementById('stable-install-btn').setAttribute('manifest', stableUrl);

    // Update button label
    const tagName = selectedRelease.tag_name;
    const preLabel = selectedRelease.prerelease ? ' (Beta)' : '';
    document.getElementById('stable-btn-text').textContent = `Встановити JAAM ${tagName}${preLabel}`;

    document.getElementById('install-buttons').style.display = 'block';

    // Display release notes
    displayReleaseNotes(selectedRelease);
});

// Simple markdown to HTML converter for GitHub-style markdown
function markdownToHtml(markdown) {
    if (!markdown) return '';
    
    let html = markdown;
    
    // Headers
    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
    
    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/_(.+?)_/g, '<em>$1</em>');
    
    // Code blocks with triple backticks
    html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Blockquotes
    html = html.replace(/^> (.*?)$/gm, '<blockquote>$1</blockquote>');
    html = html.replace(/<\/blockquote>\n<blockquote>/g, '\n');
    
    // Unordered lists
    html = html.replace(/^\* (.*?)$/gm, '<li>$1</li>');
    html = html.replace(/^\- (.*?)$/gm, '<li>$1</li>');
    html = html.replace(/^  \* (.*?)$/gm, '<li style="margin-left: 20px;">$1</li>');
    html = html.replace(/^  \- (.*?)$/gm, '<li style="margin-left: 20px;">$1</li>');
    html = html.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');
    html = html.replace(/<\/li>\s*<ul>/g, '<ul>');
    html = html.replace(/<\/ul>\s*<li>/g, '<li>');
    
    // Line breaks - convert paragraphs
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

// Display release notes
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    fetchReleases();
});
