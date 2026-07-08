import streamlit as st


def voucher_form(accounts: list, key_prefix: str = "vch"):
    st.subheader("Journal Entry Lines")
    if f"{key_prefix}_lines" not in st.session_state:
        st.session_state[f"{key_prefix}_lines"] = [
            {"account_id": "", "debit": 0.0, "credit": 0.0, "description": ""},
            {"account_id": "", "debit": 0.0, "credit": 0.0, "description": ""},
        ]

    account_options = {a.account_name: a.id for a in accounts}
    lines = []
    total_debit = 0.0
    total_credit = 0.0

    for i, row in enumerate(st.session_state[f"{key_prefix}_lines"]):
        cols = st.columns([3, 1, 1, 2])
        acc_name = cols[0].selectbox(
            "Account",
            list(account_options.keys()),
            key=f"{key_prefix}_acc_{i}",
        )
        debit = cols[1].number_input("Debit", min_value=0.0, key=f"{key_prefix}_d_{i}")
        credit = cols[2].number_input("Credit", min_value=0.0, key=f"{key_prefix}_c_{i}")
        desc = cols[3].text_input("Description", key=f"{key_prefix}_desc_{i}")
        total_debit += debit
        total_credit += credit
        lines.append(
            {
                "account_id": account_options[acc_name],
                "account_name": acc_name,
                "debit_amount": debit,
                "credit_amount": credit,
                "description": desc,
            }
        )

    def _add_line():
        st.session_state[f"{key_prefix}_lines"].append(
            {"account_id": "", "debit": 0.0, "credit": 0.0, "description": ""}
        )

    st.button("Add line", key=f"{key_prefix}_add", on_click=_add_line)

    balanced = abs(total_debit - total_credit) < 0.01
    if balanced:
        st.success(f"Balanced: Debit {total_debit:.2f} = Credit {total_credit:.2f}")
    else:
        st.error(
            f"System blocks posting — unbalanced totals: "
            f"Debit {total_debit:.2f} vs Credit {total_credit:.2f}"
        )

    return lines, balanced
