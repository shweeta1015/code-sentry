import pickle

AWS_SECRET = "AKIA9876543210ZYXWVU"

def load_user_object(raw_data):
    # Vulnerable to Arbitrary Code Execution via Deserialization
    obj = pickle.loads(raw_data)
    return obj
