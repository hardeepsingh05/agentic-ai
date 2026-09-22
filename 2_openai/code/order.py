from pydantic import BaseModel, Field

class Order(BaseModel):
    customer_id: str
    item: str
    total_price: float
    status: str

def group_orders_by_customer(orders: list[Order]) -> dict[str, list[Order]]:
    """ Group orders by customer_id, returning a dictionary where the keys are customer_ids and the values are lists of orders for that customer. """
    customer_ids = {order.customer_id for order in orders}
    grouped_orders = dict.fromkeys(customer_ids, [])
    for order in orders:
        grouped_orders[order.customer_id].append(order)
    return grouped_orders