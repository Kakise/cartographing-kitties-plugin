/**
 * Main application entry point.
 */

import { User } from "./types/user";
import { Product, ProductCategory } from "./types/product";
import { Order } from "./types/order";
import { ApiClient, ApiConfig } from "./services/api";
import { AuthService } from "./services/auth";
import { CartService } from "./services/cart";
import { UserProfile } from "./components/UserProfile";
import { OrderList } from "./components/OrderList";
import { ProductGrid } from "./components/ProductCard";
import { formatDate, truncateText } from "./utils/formatters";

export interface AppState {
    currentUser: User | null;
    products: Product[];
    orders: Order[];
    isLoading: boolean;
    error: string | null;
}

export class App {
    private state: AppState;
    private apiClient: ApiClient;
    private authService: AuthService;
    private cartService: CartService;

    constructor(config: ApiConfig) {
        this.apiClient = new ApiClient(config);
        this.authService = new AuthService(this.apiClient);
        this.cartService = new CartService(this.apiClient);
        this.state = {
            currentUser: null,
            products: [],
            orders: [],
            isLoading: false,
            error: null,
        };
    }

    async initialize(): Promise<void> {
        this.state.isLoading = true;
        try {
            const productsResponse = await this.apiClient.getProducts();
            if (productsResponse.ok) {
                this.state.products = productsResponse.data;
            }

            if (this.authService.isAuthenticated()) {
                const ordersResponse = await this.apiClient.getUserOrders();
                if (ordersResponse.ok) {
                    this.state.orders = ordersResponse.data;
                }
            }
        } catch (err) {
            this.state.error = "Failed to initialize application";
        } finally {
            this.state.isLoading = false;
        }
    }

    render(): string {
        if (this.state.isLoading) {
            return `<div class="loading">Loading...</div>`;
        }

        if (this.state.error) {
            return `<div class="error">${this.state.error}</div>`;
        }

        const parts: string[] = [];

        if (this.state.currentUser) {
            parts.push(
                UserProfile({
                    user: this.state.currentUser,
                    orders: this.state.orders,
                })
            );
        }

        parts.push(ProductGrid({ products: this.state.products }));

        if (this.state.orders.length > 0) {
            parts.push(OrderList({ orders: this.state.orders }));
        }

        const cartSummary = this.cartService.getSummary();
        parts.push(`<div class="cart-badge">Cart: ${cartSummary.itemCount} items (${cartSummary.formattedTotal})</div>`);

        return parts.join("\n");
    }

    getState(): AppState {
        return { ...this.state };
    }

    getCartService(): CartService {
        return this.cartService;
    }

    getAuthService(): AuthService {
        return this.authService;
    }
}

export function createApp(baseUrl: string = "http://localhost:3000/api"): App {
    return new App({ baseUrl, timeout: 5000 });
}
