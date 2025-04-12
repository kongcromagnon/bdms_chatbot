import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import firebase_admin
import json
from firebase_admin import credentials, initialize_app, firestore
import pandas as pd
import pickle

def get_documents_recursive(collection_ref):
    all_data = []

    docs = collection_ref.stream()
    for doc in docs:
        doc_data = doc.to_dict()
        doc_data['id'] = doc.id  # Optionally include the document ID

        # Check for subcollections
        subcollections = doc.reference.collections()
        for subcollection in subcollections:
            subcollection_data = get_documents_recursive(subcollection)
            doc_data[subcollection.id] = subcollection_data
        
        all_data.append(doc_data)
    
    return all_data

def get_products_collection_documents(db):
    collection_name = 'familyOrders2025'
    products_collection_ref = db.collection(collection_name)
    products_data = get_documents_recursive(products_collection_ref)
    return {collection_name: products_data}

# Function to load data (replace this with your actual data loading method)
def load_data():
    if not firebase_admin._apps:
        # Initialize the Firebase app with a service account
        # Get the Firebase credentials from Streamlit secrets
        firebase_creds = json.loads(st.secrets["firebase"]["credentials"])
        cred = credentials.Certificate(firebase_creds)
        initialize_app(cred)
    # Initialize Firestore DB
    db = firestore.client()
    # Get all documents from the 'products' collection and their subcollections
    products_collection_data = get_products_collection_documents(db)
    payment_df = pd.DataFrame()
    bulkAdding_df = pd.DataFrame()
    for order_id in products_collection_data['familyOrders2025']:
        if 'familyHistory2025' in order_id.keys():
            for history in order_id['familyHistory2025']:
                lineUid= history['lineUid']
                billDate = history['payment']['billDate']
                status = history['payment']['status']
                product_df = pd.DataFrame()
                history_df = pd.DataFrame([history['payment']])
                for product in history['bulkAdding']:
                    product_ = pd.DataFrame([product])
                    product_['lineUid'] = lineUid
                    product_['billDate'] = billDate
                    product_['status'] = status
                    bulkAdding_df = pd.concat([bulkAdding_df,product_], ignore_index=True)
                payment_ =pd.DataFrame([history['payment']])
                payment_['lineUid'] = lineUid
                payment_df = pd.concat([payment_df,payment_], ignore_index=True)

    return payment_df, bulkAdding_df
    
def main():
    st.title("Sales Dashboard")

    # Load data
    payment_df, bulkAdding_df = load_data()

    # Convert billDate to datetime
    payment_df['billDate'] = pd.to_datetime(payment_df['billDate'], format='%d-%m-%Y %H:%M:%S')
    bulkAdding_df['billDate'] = pd.to_datetime(bulkAdding_df['billDate'], format='%d-%m-%Y %H:%M:%S')

    # 1. Total sale amount and commission (only status = success)
    successful_sales = payment_df[payment_df['status'] == 'success']
    total_sales = successful_sales['amount'].sum()
    total_commission = total_sales * 0.05  # 5% commission

    st.header("1. Total Sales Amount and Commission")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Sales (Successful)", f"฿{total_sales:,.2f}")
    with col2:
        st.metric("Total Commission (5%)", f"฿{total_commission:,.2f}")

    # New: Line chart for daily sales amount
    st.header("Daily Sales Amount")
    daily_sales = successful_sales.groupby(successful_sales['billDate'].dt.date)['amount'].sum().reset_index()
    daily_sales.columns = ['Date', 'Sales Amount']

    fig_line = px.line(daily_sales, x='Date', y='Sales Amount',
                       title='Daily Sales Amount (Successful Transactions)',
                       labels={'Sales Amount': 'Sales Amount (฿)'})
    fig_line.update_xaxes(rangeslider_visible=True)
    st.plotly_chart(fig_line)

    # 2. Time to buy in heatmap x = Day (mon-sun) y = Time
    st.header("2. Purchase Time Heatmap")
    
    # Prepare data for heatmap
    bulkAdding_df['day'] = bulkAdding_df['billDate'].dt.day_name()
    bulkAdding_df['hour'] = bulkAdding_df['billDate'].dt.hour
    
    heatmap_data = bulkAdding_df.groupby(['day', 'hour']).size().unstack(fill_value=0)
    
    # Reorder days
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    heatmap_data = heatmap_data.reindex(day_order)
    
    # Create heatmap
    fig = px.imshow(heatmap_data, 
                    labels=dict(x="Hour of Day", y="Day of Week", color="Number of Purchases"),
                    x=heatmap_data.columns, 
                    y=heatmap_data.index,
                    aspect="auto")
    fig.update_layout(title="Purchase Time Heatmap")
    st.plotly_chart(fig)

    # 3. Most package sold (only status = success)
    st.header("3. Most Sold Packages")
    
    successful_packages = bulkAdding_df[bulkAdding_df['status'] == 'success']
    package_sales = successful_packages.groupby('packageName')['qty'].sum().sort_values(ascending=False)
    
    fig = px.bar(package_sales, x=package_sales.index, y='qty',
                 labels={'qty': 'Quantity Sold', 'packageName': 'Package Name'},
                 title="Most Sold Packages")
    st.plotly_chart(fig)

if __name__ == "__main__":
    main()
