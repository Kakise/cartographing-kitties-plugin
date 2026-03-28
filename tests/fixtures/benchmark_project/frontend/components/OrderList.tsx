/**
 * OrderList component for displaying a list of orders.
 */

import { Order, OrderStatus, getOrderStatusLabel, isOrderEditable, calculateOrderTotal } from "../types/order";
import { formatUserDisplayName } from "../types/user";
import { formatPrice } from "../types/product";

export interface OrderListProps {
    orders: Order[];
    onSelectOrder?: (order: Order) => void;
    onCancelOrder?: (orderId: number) => void;
    showUserInfo?: boolean;
}

export function OrderList(props: OrderListProps): string {
    const { orders, showUserInfo = false } = props;

    if (orders.length === 0) {
        return `<div class="empty-state">No orders found</div>`;
    }

    const rows = orders.map((order) => OrderRow({ order, showUserInfo })).join("");
    return `
        <div class="order-list">
            <table>
                <thead>
                    <tr>
                        <th>Order #</th>
                        ${showUserInfo ? "<th>Customer</th>" : ""}
                        <th>Items</th>
                        <th>Total</th>
                        <th>Status</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

export function OrderRow(props: { order: Order; showUserInfo?: boolean }): string {
    const { order, showUserInfo = false } = props;
    const statusLabel = getOrderStatusLabel(order.status);
    const editable = isOrderEditable(order);
    const total = formatPrice(order.total);

    return `
        <tr class="order-row ${editable ? "editable" : ""}">
            <td>#${order.id}</td>
            ${showUserInfo ? `<td>${formatUserDisplayName(order.user)}</td>` : ""}
            <td>${order.items.length} items</td>
            <td>${total}</td>
            <td><span class="status-badge status-${order.status}">${statusLabel}</span></td>
            <td>${new Date(order.createdAt).toLocaleDateString()}</td>
        </tr>
    `;
}

export function OrderSummary(props: { order: Order }): string {
    const { order } = props;
    const items = order.items
        .map(
            (item) =>
                `<li>${item.product.name} x${item.quantity} = ${formatPrice(item.subtotal)}</li>`
        )
        .join("");

    return `
        <div class="order-summary">
            <h3>Order #${order.id}</h3>
            <ul>${items}</ul>
            <div class="total">Total: ${formatPrice(order.total)}</div>
            <div class="status">Status: ${getOrderStatusLabel(order.status)}</div>
        </div>
    `;
}
