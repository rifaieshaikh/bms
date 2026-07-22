import streamlit as st

from vaybooks.bms.application.parties.customers.service import CustomerAppService
from vaybooks.bms.domain.parties.customers.entities import CustomerInput


def customer_selector(services: dict, key_prefix: str = "cust"):
    customer_service: CustomerAppService = services["customers"]
    search = st.text_input("Search customer by name or phone", key=f"{key_prefix}_search")
    customers = customer_service.search_customers(search)

    selected_id = None
    if customers:
        options = {
            f"{c.customer_name} - {c.phone_number}": c.id for c in customers
        }
        choice = st.selectbox("Select customer", list(options.keys()), key=f"{key_prefix}_sel")
        selected_id = options[choice]

    with st.expander("Create new customer"):
        name = st.text_input("Customer name", key=f"{key_prefix}_new_name")
        phone = st.text_input("Phone number", key=f"{key_prefix}_new_phone")
        if st.button("Create Customer", key=f"{key_prefix}_create"):
            if name and phone:
                customer = customer_service.create_customer(
                    CustomerInput(customer_name=name, phone_number=phone)
                )
                st.success(f"Created {customer.customer_name}")
                selected_id = customer.id
            else:
                st.error("Name and phone are required")

    return selected_id
