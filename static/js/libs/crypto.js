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

// set all the data in the database object store
function setData(db, store, data) {
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([store], "readwrite");
        const objectStore = transaction.objectStore(store);

        objectStore.clear();

        const request = objectStore.add(data);

        request.onsuccess = () => {
            resolve("Data successfully updated.");
        };

        request.onerror = (event) => {
            reject("Error setting data in store:", event.target.error);
        };
    });
}

// Get all data from the database from a data store
function getData(db, store) {
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([store], "readonly");
        const objectStore = transaction.objectStore(store);
        
        const request = objectStore.getAll();
        
        request.onsuccess = function(event) {
            resolve(event.target.result);
        };

        request.onerror = function(event) {
            reject(new Error("Error fetching data from store: " + event.target.error));
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