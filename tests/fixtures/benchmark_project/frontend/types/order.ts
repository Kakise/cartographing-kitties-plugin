/**
 * Order-related type definitions.
 */

import { User, UserID } from "./user";
import { Product, ProductID } from "./product";

export enum OrderStatus {
    Pending = "pending",
    Confirmed = "confirmed",
    Shipped = "shipped",
    Delivered = "delivered",
    Cancelled = "cancelled",
}

export interface OrderItem {
    product: Product;
    quantity: number;
    subtotal: number;
}

export interface Order {
    id: number;
    user: User;
    items: OrderItem[];
    total: number;
    status: OrderStatus;
    createdAt: string;
    notes?: string;
}

export type OrderID = number;

export interface CreateOrderRequest {
    userId: UserID;
}

export interface AddItemRequest {
    productId: ProductID;
    quantity?: number;
}

export function calculateOrderTotal(items: OrderItem[]): number {
    return items.reduce((sum, item) => sum + item.subtotal, 0);
}

export function isOrderEditable(order: Order): boolean {
    return order.status === OrderStatus.Pending;
}

export function getOrderStatusLabel(status: OrderStatus): string {
    const labels: Record<OrderStatus, string> = {
        [OrderStatus.Pending]: "Pending",
        [OrderStatus.Confirmed]: "Confirmed",
        [OrderStatus.Shipped]: "Shipped",
        [OrderStatus.Delivered]: "Delivered",
        [OrderStatus.Cancelled]: "Cancelled",
    };
    return labels[status];
}
