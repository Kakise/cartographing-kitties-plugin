/**
 * Product-related type definitions.
 */

export enum ProductCategory {
    Electronics = "electronics",
    Clothing = "clothing",
    Food = "food",
    Books = "books",
    Other = "other",
}

export interface Product {
    id: number;
    name: string;
    price: number;
    category: ProductCategory;
    description?: string;
    stockCount: number;
}

export type ProductID = number;

export interface CreateProductRequest {
    name: string;
    price: number;
    category?: ProductCategory;
    description?: string;
}

export function formatPrice(price: number, currency: string = "USD"): string {
    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency,
    }).format(price);
}

export function isInStock(product: Product): boolean {
    return product.stockCount > 0;
}
