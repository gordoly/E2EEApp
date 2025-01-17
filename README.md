# End to End Encrypted Chat Application

## About

This project is an end-to-end encrypted chat application designed to ensure that messages sent between two users are encrypted such that not even the server can read these messages. This project utilises the Django framework to develop the server which handles web requests and socket messages from clients, while Jinja was used to render the front end templates. A Sqlite database is used to store user accounts, the chat rooms the users of part of, and friend requests sent between users. Users can also communicate directly with one another or inside a group chat with multiple users.

## Security Features

- User passwords are stored hashed and salted on the database.
- A password policy is enforced to ensure users only use strong passwords which are not easy to guess.
- Each user generates a Diffie-Hellman key pair on the client side, using the Web Crypto API.
- Users in the same chat room perform a Diffie-Hellman key exchange to securely derive a shared secret between each pair of users, ensuring that the server cannot decrypt messages.
- Messages are encrypted using AES-GCM with the shared secret, ensuring both confidentiality and integrity of the messages.
- Message histories are not stored on the server. If a user is offline, messages for them are temporarily stored and deleted upon delivery. These messages are encrypted while stored on the server.
- The user's Diffie-Hellman secret and message histories are all stored on the user's browser using IndexDB.
- A PBKDF2 key is derived from the user's password which is used to encrypt all data stored within IndexDB. The user's password is only ever obtained via user input.
- When a user returns online and retrieves stored messages, a new Diffie-Hellman key pair is generated to maintain forward secrecy.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/gordoly/E2EEApp.git
    cd E2EEApp
    ```

2. Ensure Redis and Python3 are installed and running on your system. If either of these are not yet installed on your system: 

    - Python3 can be installed [here](https://www.python.org/downloads/).

    - Redis is used as the message broker for Django Channels in this application. Follow the instructions [here](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/) to install Redis.

3. Install the Python dependences:
    ```bash
    pip3 install -r requirements.txt
    ```

## Usage

First ensure Redis is running on your system.

Then, to start the web server, run the command:
```bash
daphne EncryptedChatApp.asgi:application
```

Then visit the site at http://127.0.0.1:8000.
