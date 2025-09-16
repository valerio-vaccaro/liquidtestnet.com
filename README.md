# 🌊 Liquid Testnet Faucet

<div align="center">

![Liquid Network](https://img.shields.io/badge/Liquid-Network-blue?style=for-the-badge&logo=bitcoin)
![Python](https://img.shields.io/badge/Python-3.8+-green?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-2.0+-red?style=for-the-badge&logo=flask)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**A comprehensive Liquid Network testnet faucet and explorer with asset issuance capabilities, powered by LWK (Liquid Wallet Kit)**

[🚀 Features](#-features) • [⚙️ Installation](#️-installation) • [🔧 Configuration](#-configuration) • [🏃‍♂️ Usage](#️-usage) • [📡 API](#-api) • [🔗 Links](#-links)

</div>

---

## ✨ Features

### 🎯 **Multi-Asset Faucet (LWK-Powered)**
- 💰 **LBTC Faucet** - Get Liquid Bitcoin testnet coins via LWK
- 🧪 **Test Asset Faucet** - Receive custom test assets using LWK
- ⚡ **AMP Asset Faucet** - Access AMP tokens
- 🛡️ **Rate Limiting** - Built-in protection against abuse
- 🔧 **LWK Integration** - All transactions powered by Liquid Wallet Kit

### 🔍 **Block Explorer**
- 📊 **Real-time Stats** - Blockchain height, mempool size, disk usage
- 🧱 **Block Explorer** - Browse blocks with transaction details
- 💾 **Mempool Viewer** - Monitor pending transactions
- 🔗 **Transaction Details** - Full transaction information

### 🏭 **Asset Issuance (LWK-Native)**
- 🎨 **Custom Assets** - Create your own Liquid assets using LWK
- 🔐 **Reissuance Tokens** - Control asset supply with LWK
- 📝 **Contract Support** - Define asset metadata and properties
- 🌐 **Domain Verification** - Link assets to domains
- ✅ **Pre-configured Domain** - Use `liquidtestnet.com` as a valid domain for any test token
- ⚡ **LWK Transaction Builder** - Native LWK transaction construction

### 🛠️ **Utilities**
- 📤 **Transaction Broadcasting** - Submit raw transactions
- ✅ **Mempool Testing** - Validate transactions before broadcast
- 📋 **OP_RETURN Support** - Store data on-chain

---

## ⚙️ Installation

### Prerequisites
- Python 3.8 or higher
- Liquid Elements node (testnet)
- **LWK (Liquid Wallet Kit)** - Core dependency for all Liquid operations

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-username/liquidtestnet.com.git
cd liquidtestnet.com

# 2. Create virtual environment
python3 -m venv venv3
source venv3/bin/activate  # On Windows: venv3\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure the application (see Configuration section)
cp liquid.conf.example liquid.conf
# Edit liquid.conf with your settings

# 5. Run the application
python faucet.py
```

### Dependencies
- **LWK (Liquid Wallet Kit)** - ⭐ **Core engine** for all Liquid operations
- **Flask** - Web framework
- **Flask-Limiter** - Rate limiting
- **WallyCore** - Bitcoin/Liquid cryptographic library 
- **Bitcoin RPC** - Elements node communication

---

## 🔧 Configuration

Create a `liquid.conf` file with the following structure:

```ini
[GENERAL]
liquid_instance: LIQUID

[LIQUID]
host: localhost
port: 7041
username: your_rpc_username
password: your_rpc_password
wallet: your_wallet_name
passphrase: your_wallet_passphrase

[AMP]
url: https://your-amp-server.com
token: your_amp_token
assetuuid: your_asset_uuid

[LWK]
mnemonic: your_lwk_mnemonic_phrase
address: your_lwk_address
```

### 🎯 **Simplified Token Issuance**

For easy test token creation, you can use `liquidtestnet.com` as a pre-validated domain:

```bash
# Example: Create a test token using liquidtestnet.com domain
curl "http://localhost:8123/api/issuer?command=asset&asset_amount=1000&asset_address=tlq1q...&token_amount=100&token_address=tlq1q...&pubkey=02...&name=MyTestToken&ticker=MTT&precision=8&domain=liquidtestnet.com"
```

**LWK Benefits:**
- ⚡ **Native Liquid Support** - Built specifically for Liquid Network
- 🔐 **Secure Transaction Building** - LWK handles all cryptographic operations
- 🎯 **Simplified API** - No need to understand low-level Liquid protocols
- ✅ **Pre-validated Domain** - Eliminates domain verification setup for test tokens

This makes development and testing much faster with LWK's streamlined approach!

## 🏃‍♂️ Usage

### Starting the Server

```bash
# Activate virtual environment
source venv3/bin/activate

# Start the faucet server
python faucet.py
```

The server will start on `http://0.0.0.0:8123`

### Web Interface

| Endpoint | Description |
|----------|-------------|
| `/` | Home page with blockchain stats |
| `/faucet` | Multi-asset faucet interface |
| `/explorer` | Block explorer |
| `/mempool` | Mempool transaction viewer |
| `/issuer` | Asset issuance interface |
| `/utils` | Transaction utilities |
| `/about` | About page |

---

## 📡 API

### Faucet Endpoints

#### Get Faucet Status
```http
GET /api/faucet?address=your_address&action=lbtc
```

**Parameters:**
- `address` - Liquid address to receive funds
- `action` - Asset type (`lbtc`, `test`, `amp`)

**Response:**
```json
{
  "result": "Sent 100000 LBTC to address tlq1q...",
  "balance": 5000000,
  "balance_test": 1000000,
  "balance_amp": 100
}
```

#### Asset Issuance
```http
GET /api/issuer?command=asset&asset_amount=1000&asset_address=tlq1q...&token_amount=100&token_address=tlq1q...&pubkey=02...&name=MyAsset&ticker=MA&precision=8&domain=liquidtestnet.com
```

**💡 Pro Tip**: You can use `liquidtestnet.com` as the domain for any test token issuance. This domain is pre-configured and validated, making it easy to create test assets with LWK without needing to set up your own domain verification.

### Explorer Endpoints

#### Blockchain Stats
```http
GET /api/stats
```

#### Block Information
```http
GET /api/block?height=12345
```

#### Transaction Details
```http
GET /api/transaction?txid=abc123...
```

#### Mempool
```http
GET /api/mempool
```

---

## 🔗 Links

- 🌐 **Live Site**: [liquidtestnet.com](https://liquidtestnet.com)
- 📚 **Liquid Network**: [liquid.net](https://liquid.net)
- 🛠️ **Elements Project**: [github.com/ElementsProject/elements](https://github.com/ElementsProject/elements)
- 💼 **LWK Documentation**: [github.com/Blockstream/lwk](https://github.com/Blockstream/lwk) - **Core technology powering this faucet**

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This is a **testnet faucet** for development and testing purposes only. The assets distributed have no real value and should not be used for production applications.

---

<div align="center">

**Made with ❤️ for the Liquid Network community using LWK (Liquid Wallet Kit)**

[🔝 Back to Top](#-liquid-testnet-faucet)

</div>
