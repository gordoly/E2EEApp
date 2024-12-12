// Generate random bytes for salt and iv
function generateRandomBytes(length) {
    const array = new Uint8Array(length);
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

// generate an ECDH key pair
async function generateKeyPair() {
    const keyPair = await crypto.subtle.generateKey(
        {
            name: "ECDH",
            namedCurve: "P-256",
        },
        true,
        ["deriveKey", "deriveBits"]
    );
    return keyPair;
}

// encrypt the private key of the ECDH key pair
async function encryptPrivateKey(privateKey, passDerivedKey, iv) {
    const exported = await crypto.subtle.exportKey("pkcs8", privateKey);
    const encryptedKey = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        exported
    );
    return encryptedKey;
}

// decrypt the private key of the ECDH key pair
async function decryptPrivateKey(encryptedKey, passDerivedKey, iv) {
    const decryptedKey = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        encryptedKey
    );

    const importedKey = await crypto.subtle.importKey(
        'pkcs8',
        decryptedKey,
        {
            name: "ECDH",
            namedCurve: "P-256",
        },
        true,
        ["deriveKey", "deriveBits"]
    );

    return importedKey;
}

// encrypt message history stored on IndexDB using password derived key
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

// decrypt message history stored on IndexDB using password derived key
async function decryptMsgHistory(msgHistory, passDerivedKey, iv) {
    const decryptedMsgHistory = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        msgHistory
    );
    const decoded = new TextDecoder().decode(decryptedMsgHistory);
    return JSON.parse(decoded);
}

// derive shared key using Diffe Hellman
async function deriveSharedSecret(privateKey, publicKey) {
    const sharedSecret = await crypto.subtle.deriveBits(
      {
        name: "ECDH",
        private: privateKey,
        public: publicKey
      },
      privateKey,
      256
    );

    const symmetricKey = await crypto.subtle.importKey(
        "raw", 
        sharedSecret,
        { name: "AES-GCM" },
        true,
        ["encrypt", "decrypt"]
    );

    return symmetricKey;
  }

// encrypt a string using a shared Diffe Hellman key
async function encryptMessage(message, symmetricKey) {
    const msgIv = generateRandomBytes(12);
    
    const encrypted = await crypto.subtle.encrypt(
        {
            name: "AES-GCM",
            iv: msgIv,
        },
        symmetricKey,
        new TextEncoder().encode(message)
    );
  
    return { encrypted, msgIv };
}

// decrypt a string using a shared Diffe Hellman key
async function decryptMessage(symmetricKey, iv, encrypted) {
    const decrypted = await crypto.subtle.decrypt(
        {
            name: "AES-GCM",
            iv: iv,
        },
        symmetricKey,
        encrypted
    );
 
    return new TextDecoder().decode(decrypted);
}