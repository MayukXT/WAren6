function rawPhonePart(value) {
    return String(value || '').split('@')[0].replace(/^\+/, '').trim();
}

export function phoneDigits(value) {
    return rawPhonePart(value).replace(/[^\d]/g, '');
}

const COUNTRY_CODES = new Set([
    '1', '7',
    '20', '27', '30', '31', '32', '33', '34', '36', '39', '40', '41', '43', '44', '45', '46', '47', '48', '49',
    '51', '52', '53', '54', '55', '56', '57', '58',
    '60', '61', '62', '63', '64', '65', '66',
    '81', '82', '84', '86',
    '90', '91', '92', '93', '94', '95', '98',
    '211', '212', '213', '216', '218', '220', '221', '222', '223', '224', '225', '226', '227', '228', '229',
    '230', '231', '232', '233', '234', '235', '236', '237', '238', '239', '240', '241', '242', '243', '244',
    '245', '246', '248', '249', '250', '251', '252', '253', '254', '255', '256', '257', '258', '260', '261',
    '262', '263', '264', '265', '266', '267', '268', '269',
    '290', '291', '297', '298', '299',
    '350', '351', '352', '353', '354', '355', '356', '357', '358', '359',
    '370', '371', '372', '373', '374', '375', '376', '377', '378', '380', '381', '382', '383', '385', '386',
    '387', '389',
    '420', '421', '423',
    '500', '501', '502', '503', '504', '505', '506', '507', '508', '509',
    '590', '591', '592', '593', '594', '595', '596', '597', '598', '599',
    '670', '672', '673', '674', '675', '676', '677', '678', '679', '680', '681', '682', '683', '685', '686',
    '687', '688', '689', '690', '691', '692',
    '850', '852', '853', '855', '856',
    '880', '886',
    '960', '961', '962', '963', '964', '965', '966', '967', '968', '970', '971', '972', '973', '974', '975',
    '976', '977', '992', '993', '994', '995', '996', '998',
]);

function splitCountryCode(digits) {
    if (!digits || digits.length <= 10) return { country: '', local: digits };
    for (let size = 3; size >= 1; size -= 1) {
        const candidate = digits.slice(0, size);
        if (COUNTRY_CODES.has(candidate)) {
            return { country: candidate, local: digits.slice(size) };
        }
    }
    const fallbackLength = Math.max(1, digits.length - 10);
    return { country: digits.slice(0, fallbackLength), local: digits.slice(fallbackLength) };
}

function groupLocalNumber(local, country) {
    if (!local) return [];

    if (country === '91' && local.length === 10) {
        return [local.slice(0, 5), local.slice(5)];
    }

    if (country === '1' && local.length === 10) {
        return [local.slice(0, 3), local.slice(3, 6), local.slice(6)];
    }

    if (!country && local.length === 10) {
        return [local.slice(0, 3), local.slice(3, 6), local.slice(6)];
    }

    if (local.length <= 4) return [local];
    if (local.length <= 7) return [local.slice(0, local.length - 4), local.slice(-4)];
    if (local.length === 8) return [local.slice(0, 4), local.slice(4)];

    const tail = local.slice(-4);
    const rest = local.slice(0, -4);
    const groups = [];
    const first = rest.length % 3 || 3;
    groups.push(rest.slice(0, first));
    for (let i = first; i < rest.length; i += 3) {
        groups.push(rest.slice(i, i + 3));
    }
    groups.push(tail);
    return groups.filter(Boolean);
}

export function compactPhoneNumber(value) {
    const digits = phoneDigits(value);
    return digits ? `+${digits}` : null;
}

export function formatPhoneNumber(value) {
    const digits = phoneDigits(value);
    if (!digits) return null;

    const { country, local } = splitCountryCode(digits);
    const grouped = groupLocalNumber(local, country).join(' ');
    return country ? `+${country} ${grouped}`.trim() : grouped;
}
