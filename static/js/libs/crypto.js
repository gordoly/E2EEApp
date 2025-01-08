/**
 * Generate random bytes for salt and iv 
 * @param {Number} length 
 * @returns an array of random bytes
 */
function generateRandomBytes(length) {
    const array = new Uint8Array(length);
    window.crypto.getRandomValues(array);
    return array;
}

/**
 * Open an IndexDB Database, creating appriopriate object stores to store message
 * histories and key data if they do not exist.
 * @returns a promise that resolves to the database object
 */
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

/**
 * Add data to the database object store 
 * @param {*} db the IndexDB database object
 * @param {*} store the object store to add the data to
 * @param {*} data the data to add to the object store
 * @returns a promise that resolves to a success message or rejects with an error message
 */
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

/**
 * Set the data in the database object store where the id = owner 
 * @param {*} db the IndexDB database object
 * @param {*} store the object store to add the data to
 * @param {*} data the data that the object store will be set to
 * @param {*} owner the primary key of the data to be set, which corresponds to
 * the username of the user who owns the data
 * @returns a promise that resolves to a success message or rejects with an error message
 */
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

/**
 * Get all data from the database from a data store where the id = owner 
 * @param {*} db the IndexDB database object
 * @param {*} store the object store to get the data from
 * @param {*} owner the primary key of the data to be retrieved, which corresponds to
 * the username of the user who owns the data 
 * @returns the data from the object store
 */
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

/**
 * Generate an Elliptic Curve Diffie-Hellman key pair 
 * @returns key pair object containing the Diffie-Hellman public and private keys
 */
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

/**
 * Encrypt the private key of the ECDH key pair 
 * @param {*} privateKey the ECDH private key to be encrypted
 * @param {*} passDerivedKey the password derived key used to encrypt the private key
 * @param {*} iv the initialization vector used to encrypt the private key
 * @returns the encrypted private key
 */
async function encryptPrivateKey(privateKey, passDerivedKey, iv) {
    const exported = await crypto.subtle.exportKey("pkcs8", privateKey);
    const encryptedKey = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        exported
    );
    return encryptedKey;
}

/**
 * Decrypt the private key of the ECDH key pair 
 * @param {*} encryptedKey the encrypted Diffie-Hellman private key to be decrypted
 * @param {*} passDerivedKey the password derived key used to encrypt the private key 
 * @param {*} iv the initialization vector used to encrypt the private key
 * @returns the decrypted private key
 */
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

/**
 * Encrypt message history stored on IndexDB using password derived key 
 * @param {*} msgHistory the message history of all chat rooms that the user is part of
 * which is to be encrypted
 * @param {*} passDerivedKey the password derived key used to encrypt the message history
 * @param {*} iv the initialization vector used to encrypt the message history
 * @returns the encrypted message history
 */
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

/**
 * Decrypt message history stored on IndexDB using password derived key 
 * @param {*} msgHistory the encrypted message history of all chat rooms that the user is part of
 * @param {*} passDerivedKey the password derived key used to encrypt the message history
 * @param {*} iv the initialization vector used to encrypt the message history
 * @returns the decrypted message history
 */
async function decryptMsgHistory(msgHistory, passDerivedKey, iv) {
    const decryptedMsgHistory = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: new TextEncoder().encode(iv) },
        passDerivedKey,
        msgHistory
    );
    const decoded = new TextDecoder().decode(decryptedMsgHistory);
    return JSON.parse(decoded);
}

/**
 * Derive shared key using ECDH
 * @param {*} privateKey the private key of the user
 * @param {*} publicKey the public key of the user who the user is communicating with
 * @returns the shared key derived using ECDH
 */
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

/**
 * Encrypt a string using a shared Diffe Hellman key 
 * @param {*} message the message to be encrypted
 * @param {*} symmetricKey the shared Diffie-Hellman key used to encrypt the message
 * @returns the encrypted message as an array of bytes and the initialization vector 
 * used to encrypt the message
 */
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

/**
 * Decrypt a string using a shared Diffe Hellman key 
 * @param {*} symmetricKey the shared Diffie-Hellman key used to encrypt/decrypt the message
 * @param {*} iv the initialization vector used to encrypt the message
 * @param {*} encrypted the encrypted message to be decrypted
 * @returns a string containing the decrypted message
 */
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