/**
 * HTTP API client for communicating with the backend.
 */

import { User, CreateUserRequest, UpdateUserRequest } from "../types/user";
import { Product, CreateProductRequest } from "../types/product";
import { Order, CreateOrderRequest, AddItemRequest } from "../types/order";

export interface ApiConfig {
    baseUrl: string;
    timeout: number;
    authToken?: string;
}

export interface ApiResponse<T> {
    data: T;
    status: number;
    ok: boolean;
}

export class ApiClient {
    private config: ApiConfig;

    constructor(config: ApiConfig) {
        this.config = config;
    }

    private getHeaders(): Record<string, string> {
        const headers: Record<string, string> = {
            "Content-Type": "application/json",
        };
        if (this.config.authToken) {
            headers["Authorization"] = `Bearer ${this.config.authToken}`;
        }
        return headers;
    }

    private async request<T>(method: string, path: string, body?: unknown): Promise<ApiResponse<T>> {
        const url = `${this.config.baseUrl}${path}`;
        const response = await fetch(url, {
            method,
            headers: this.getHeaders(),
            body: body ? JSON.stringify(body) : undefined,
        });

        const data = await response.json();
        return {
            data: data as T,
            status: response.status,
            ok: response.ok,
        };
    }

    async getUsers(): Promise<ApiResponse<User[]>> {
        return this.request<User[]>("GET", "/users");
    }

    async getUser(id: number): Promise<ApiResponse<User>> {
        return this.request<User>("GET", `/users/${id}`);
    }

    async createUser(req: CreateUserRequest): Promise<ApiResponse<User>> {
        return this.request<User>("POST", "/users", req);
    }

    async updateUser(id: number, req: UpdateUserRequest): Promise<ApiResponse<User>> {
        return this.request<User>("PUT", `/users/${id}`, req);
    }

    async getProducts(): Promise<ApiResponse<Product[]>> {
        return this.request<Product[]>("GET", "/products");
    }

    async getProduct(id: number): Promise<ApiResponse<Product>> {
        return this.request<Product>("GET", `/products/${id}`);
    }

    async createProduct(req: CreateProductRequest): Promise<ApiResponse<Product>> {
        return this.request<Product>("POST", "/products", req);
    }

    async searchProducts(query: string): Promise<ApiResponse<Product[]>> {
        return this.request<Product[]>("GET", `/products/search?q=${encodeURIComponent(query)}`);
    }

    async createOrder(req: CreateOrderRequest): Promise<ApiResponse<Order>> {
        return this.request<Order>("POST", "/orders", req);
    }

    async addItemToOrder(orderId: number, req: AddItemRequest): Promise<ApiResponse<Order>> {
        return this.request<Order>("POST", `/orders/${orderId}/items`, req);
    }

    async confirmOrder(orderId: number): Promise<ApiResponse<Order>> {
        return this.request<Order>("POST", `/orders/${orderId}/confirm`);
    }

    async getUserOrders(): Promise<ApiResponse<Order[]>> {
        return this.request<Order[]>("GET", "/orders");
    }
}
