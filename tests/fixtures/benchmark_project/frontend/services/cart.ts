/**
 * Shopping cart service for managing cart state.
 */

import { Product, ProductID, isInStock, formatPrice } from "../types/product";
import { OrderItem, calculateOrderTotal } from "../types/order";
import { ApiClient } from "./api";

export interface CartItem {
    product: Product;
    quantity: number;
}

export interface CartSummary {
    items: CartItem[];
    itemCount: number;
    total: number;
    formattedTotal: string;
}

export class CartService {
    private items: Map<ProductID, CartItem> = new Map();
    private apiClient: ApiClient;

    constructor(apiClient: ApiClient) {
        this.apiClient = apiClient;
    }

    addItem(product: Product, quantity: number = 1): boolean {
        if (!isInStock(product)) {
            return false;
        }

        const existing = this.items.get(product.id);
        if (existing) {
            existing.quantity += quantity;
        } else {
            this.items.set(product.id, { product, quantity });
        }
        return true;
    }

    removeItem(productId: ProductID): boolean {
        return this.items.delete(productId);
    }

    updateQuantity(productId: ProductID, quantity: number): boolean {
        const item = this.items.get(productId);
        if (!item) return false;

        if (quantity <= 0) {
            return this.removeItem(productId);
        }

        item.quantity = quantity;
        return true;
    }

    getItems(): CartItem[] {
        return Array.from(this.items.values());
    }

    getItemCount(): number {
        let count = 0;
        for (const item of this.items.values()) {
            count += item.quantity;
        }
        return count;
    }

    getTotal(): number {
        let total = 0;
        for (const item of this.items.values()) {
            total += item.product.price * item.quantity;
        }
        return Math.round(total * 100) / 100;
    }

    getSummary(): CartSummary {
        const total = this.getTotal();
        return {
            items: this.getItems(),
            itemCount: this.getItemCount(),
            total,
            formattedTotal: formatPrice(total),
        };
    }

    clear(): void {
        this.items.clear();
    }

    isEmpty(): boolean {
        return this.items.size === 0;
    }

    async checkout(): Promise<boolean> {
        if (this.isEmpty()) return false;

        try {
            const orderResponse = await this.apiClient.createOrder({ userId: 0 });
            if (!orderResponse.ok) return false;

            for (const item of this.items.values()) {
                await this.apiClient.addItemToOrder(orderResponse.data.id, {
                    productId: item.product.id,
                    quantity: item.quantity,
                });
            }

            await this.apiClient.confirmOrder(orderResponse.data.id);
            this.clear();
            return true;
        } catch {
            return false;
        }
    }
}
