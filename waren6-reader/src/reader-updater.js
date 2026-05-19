export const CURRENT_READER_VERSION = '1.7.0';
export const RELEASE_METADATA_URL = 'https://raw.githubusercontent.com/MayukXT/WAren6/reader-latest/WAren6-Reader-latest.json';
export const RELEASE_PAGE_URL = 'https://github.com/MayukXT/WAren6/releases?q=reader-v&expanded=true';

function normalizeVersion(version) {
    return String(version || '')
        .trim()
        .replace(/^v/i, '')
        .split(/[+-]/)[0]
        .split('.')
        .map(part => Number.parseInt(part, 10) || 0);
}

export function compareVersions(left, right) {
    const a = normalizeVersion(left);
    const b = normalizeVersion(right);
    const width = Math.max(a.length, b.length, 3);

    for (let i = 0; i < width; i += 1) {
        const delta = (a[i] || 0) - (b[i] || 0);
        if (delta > 0) return 1;
        if (delta < 0) return -1;
    }
    return 0;
}

function portableAssetFromManifest(manifest) {
    return manifest?.assets?.reader_portable || null;
}

export function buildPortableUpdateRequest(manifest) {
    const asset = portableAssetFromManifest(manifest);
    if (!manifest?.version || !asset?.url || !asset?.sha256) {
        throw new Error('Portable Reader update metadata is incomplete.');
    }

    return {
        downloadUrl: asset.url,
        sha256: asset.sha256,
        version: manifest.version,
    };
}

export async function checkForReaderUpdate({
    currentVersion = CURRENT_READER_VERSION,
    metadataUrl = RELEASE_METADATA_URL,
    fetchImpl = fetch,
} = {}) {
    try {
        const response = await fetchImpl(metadataUrl, { cache: 'no-store' });
        if (!response.ok) {
            throw new Error(`Release metadata returned HTTP ${response.status}`);
        }

        const manifest = await response.json();
        const latestVersion = manifest.version || '';
        if (!latestVersion) {
            throw new Error('Release metadata does not include a version.');
        }

        return {
            status: compareVersions(latestVersion, currentVersion) > 0 ? 'available' : 'current',
            latestVersion,
            latestDate: manifest.release_date || '',
            releaseUrl: manifest.release_url || RELEASE_PAGE_URL,
            changelog: manifest.changelog || '',
            portableAsset: portableAssetFromManifest(manifest),
            manifest,
        };
    } catch (error) {
        return {
            status: 'failed',
            error: error instanceof Error ? error.message : String(error),
            releaseUrl: RELEASE_PAGE_URL,
        };
    }
}

export async function installInstalledUpdate(invokeFn) {
    await invokeFn('install_installed_update');
    return { status: 'installed' };
}

export async function installPortableUpdate(invokeFn, manifest) {
    await invokeFn('install_portable_update', buildPortableUpdateRequest(manifest));
    return { status: 'portable' };
}

export async function openReleasePage(openUrl = globalThis.window?.__TAURI__?.opener?.openUrl) {
    if (typeof openUrl === 'function') {
        await openUrl(RELEASE_PAGE_URL);
        return;
    }
    globalThis.window?.open(RELEASE_PAGE_URL, '_blank', 'noopener,noreferrer');
}

export function updateStatusText(status) {
    switch (status) {
        case 'checking':
            return 'Checking for updates...';
        case 'current':
            return 'You are up to date.';
        case 'available':
            return 'Update available.';
        case 'failed':
            return 'Update check failed.';
        case 'installing':
            return 'Installing update...';
        case 'installed':
            return 'Update installed. Restarting Reader...';
        case 'portable':
            return 'Portable update ready. Reader will restart after replacement.';
        default:
            return 'Update status unknown.';
    }
}
