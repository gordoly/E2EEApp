# End to End Encrypted Chat Application

## About

This project is an end-to-end encrypted chat application designed to ensure that messages sent between two users are encrypted such that not even the server can read these messages. This project utilises the Django framework to develop the server which handles web requests and socket messages from clients, while Jinja was used to render the front end templates. The application manages the usage of Diffie-Hellman keys which are used to encrypt and decrypt messages sent between users. The application encrypts, using PBKDF2 keys which are derived from the user's password, the user's Diffie-Hellman cryptographic keys and message histories. These are then stored locally on the user's browser using IndexDB. Messages are only stored on the server if the receiver is offline, however, once the receiver is able to receive messages, the stored messages will be removed from the server's database.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/gordoly/E2EEApp.git
    cd E2EEApp
    ```

2. Ensure Redis is installed and running on your system. Redis is used as the message broker for Django Channels in this application. Follow the instructions [here](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/) to install Redis if it is not yet installed on your system.

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