# issue_observatory_search 0.1

clone library and install to start using.

## 🚀 Getting Started

  1. Install dependencies: pip install -r requirements.txt
  2. Configure environment: Copy config/.env.example to config/.env
  3. Create a user: python create_user.py username email password
  4. Run the app: python app.py


## 🚀 Next Steps

  1. For Production: Generate a secure secret key:
  python -c "import secrets; print(secrets.token_hex(32))"
  2. Test the Configuration: Run the application to verify everything works:
  python app.py
  3. Create Your First User:
  python create_user.py yourusername your@email.com yourpassword