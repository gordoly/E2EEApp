// Generate random bytes for salt and iv
function generateRandomBytes() {
    const array = new Uint8Array(16);
    window.crypto.getRandomValues(array);
    return array;
}

// Open an IndexDB Database
function openDatabase() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('chatDatabase', 1);

        request.onerror = (event) => {
            reject('Database failed to open: ' + event.target.errorCode);
        };

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('messages')) {
                db.createObjectStore('messages', { keyPath: 'id' });
            }
            if (!db.objectStoreNames.contains('keys')) {
                db.createObjectStore('keys', { keyPath: 'id' });
            }
        };

        request.onsuccess = (event) => {
            resolve(event.target.result);
        };
    });
}

// Add data to the database
function addData(db, store, data) {
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([store], 'readwrite');
        const objectStore = transaction.objectStore(store);

        const request = objectStore.add(data);

        request.onsuccess = () => {
            resolve('Data added successfully');
        };

        request.onerror = (event) => {
            reject('Error adding data: ' + event.target.errorCode);
        };
    });
}

// set the data in the database object store where the id = owner
function setData(db, store, data, owner) {
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([store], 'readwrite');
        const objectStore = transaction.objectStore(store);

        const request = objectStore.get(owner)

        request.onsuccess = (event) => {
            const requestedData = event.target.result;
            requestedData["content"] = data
            const putRequest = objectStore.put(requestedData);

            putRequest.onsuccess = () => {
                resolve('Data added successfully');
            };

            putRequest.onerror = (event) => {
                reject('Error adding data: ' + event.target.errorCode);
            };
        };

        request.onerror = (event) => {
            reject('Error clearing store: ' + event.target.errorCode);
        };
    });
}

// Get all data from the database from a data store where the id = owner
function getData(db, store, owner) {
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([store], 'readonly');
        const objectStore = transaction.objectStore(store);
        
        const request = objectStore.get(owner);

        request.onsuccess = (event) => {
            resolve(event.target.result || null);
        };

        request.onerror = () => {
            reject(null);
        };
    });
}

// generate an RSA key pair
async function generateKeyPair() {
    const keyPair = await crypto.subtle.generateKey(
        {
            name: "RSA-OAEP",
            modulusLength: 2048,
            publicExponent: new Uint8Array([1, 0, 1]),
            hash: { name: "SHA-256" },
        },
        true,
        ["encrypt", "decrypt"]
    );
    return keyPair;
}

// encrypt the private key of the RSA key pair
async function encryptRSAKey(privateKey, passDerivedKey, iv) {
    const exported = await crypto.subtle.exportKey("pkcs8", privateKey);
    const encryptedKey = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        exported
    );
    return encryptedKey;
}

// decrypt the private key of the RSA key pair
async function decryptRSAKey(encryptedKey, passDerivedKey, iv) {
    const decryptedKey = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        encryptedKey
    );

    const importedKey = await crypto.subtle.importKey(
        'pkcs8',
        decryptedKey,
        {
            name: 'RSA-OAEP',
            hash: 'SHA-256',
        },
        true,
        ['decrypt']
    );

    return importedKey;
}

// encrypt message history stored on IndexDB
async function encryptMsgHistory(msgHistory, passDerivedKey, iv) {
    const stringified = JSON.stringify(msgHistory);
    const encoded = new TextEncoder().encode(stringified);
    const encryptedMsgHistory = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        encoded
    );
    return encryptedMsgHistory;
}

// decrypt message history stored on IndexDB
async function decryptMsgHistory(msgHistory, passDerivedKey, iv) {
    const decryptedMsgHistory = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        msgHistory
    );
    const decoded = new TextDecoder().decode(decryptedMsgHistory);
    return JSON.parse(decoded);
}

// encrypt a string using a public RSA key
async function ecryptMessage(publicKey, message) {
    const encoded = new TextEncoder().encode(message);
    
    const encrypted = await crypto.subtle.encrypt(
        { name: "RSA-OAEP" },
        publicKey,
        encoded
    );

    return encrypted;
}

// decrypt a string using a private RSA key
async function decryptMessage(privateKey, encrypted) {
    const decrypted = await crypto.subtle.decrypt(
        { name: "RSA-OAEP" },
        privateKey,
        encrypted
    );

    return new TextDecoder().decode(decrypted);
}

// hash and salt a string
async function hashWithSalt(plainText, salt) {
    const encoder = new TextEncoder();
    const textBuffer = encoder.encode(plainText);
    const combined = new Uint8Array(textBuffer.length + salt.length);

    combined.set(textBuffer);
    combined.set(salt, textBuffer.length);

    const hashBuffer = await crypto.subtle.digest('SHA-256', combined);
    
    return hashBuffer;
}

// compare a plain text with a hash to see if they are same string
async function compareHash(plainText, storedHash, storedSalt) {
    const hashToCompare = await hashWithSalt(plainText, storedSalt);
    const uint8Hash = new Uint8Array(hashToCompare);
    
    for (let i = 0; i < storedHash.length; i++) {
        if (storedHash[i] !== uint8Hash[i]) {
            return false;
        }
    }

    return true;
}