const saved = Cookies.get("saved");
const needToScrool = Cookies.get("scroll");
const reboot = Cookies.get("reboot");
const restore = Cookies.get("restore");
const restoreError = Cookies.get("restore-error");

function showToast(toastId) {
    const toast = document.getElementById(toastId);
    toast.classList.remove('hide');
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
        toast.classList.add('hide');
    }, 2000);
}

if (saved) {
    showToast('saved-toast');
    Cookies.remove("saved");
};

if (needToScrool) {
    window.scrollTo(0, document.body.scrollHeight);
    Cookies.remove("scroll");
};

if (reboot) {
    showToast('reboot-toast');
    Cookies.remove("reboot");
}

if (restore) {
    showToast('restore-toast');
    Cookies.remove("restore");
}

if (restoreError) {
    showToast('restore-error-toast');
    Cookies.remove("restore-error");
}

async function fetchReleaseNotes(version) {
    // Get the version from the input parameter if provided, otherwise from the HTML element's data attribute
    const releaseNotesElement = document.getElementById("release-notes");
    version = version || releaseNotesElement.getAttribute("data-version");

    // Construct the API URL dynamically using the version
    const apiUrl = `https://api.github.com/repos/J-A-A-M/ukraine_alarm_map/releases/tags/${version}`;

    try {
        const response = await fetch(apiUrl);

        if (!response.ok) {
            throw new Error(`Failed to fetch release notes: ${response.statusText}`);
        }

        const data = await response.json();
        const releaseNotes = data.body;

        // Format the release notes using the https://github.com/markedjs/marked library and display them in the element
        releaseNotesElement.innerHTML = marked.parse(releaseNotes);

    } catch (error) {
        releaseNotesElement.textContent = `Error: ${error.message}`;
    }
}
