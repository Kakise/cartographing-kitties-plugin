/**
 * ProductCard component for displaying product information.
 */

import { Product, ProductCategory, formatPrice, isInStock } from "../types/product";
import { CartService } from "../services/cart";

export interface ProductCardProps {
    product: Product;
    onAddToCart?: (product: Product) => void;
    showDetails?: boolean;
}

export function ProductCard(props: ProductCardProps): string {
    const { product, showDetails = true } = props;
    const price = formatPrice(product.price);
    const available = isInStock(product);
    const categoryLabel = getCategoryLabel(product.category);

    return `
        <div class="product-card ${available ? "" : "out-of-stock"}">
            <h3>${product.name}</h3>
            <span class="category">${categoryLabel}</span>
            <p class="price">${price}</p>
            ${showDetails && product.description ? `<p class="description">${product.description}</p>` : ""}
            <div class="stock-info">
                ${available ? `<span class="in-stock">In Stock (${product.stockCount})</span>` : `<span class="no-stock">Out of Stock</span>`}
            </div>
            ${available ? `<button class="add-to-cart">Add to Cart</button>` : ""}
        </div>
    `;
}

export function ProductGrid(props: { products: Product[]; columns?: number }): string {
    const { products, columns = 3 } = props;

    if (products.length === 0) {
        return `<div class="empty-state">No products found</div>`;
    }

    const cards = products.map((product) => ProductCard({ product })).join("");
    return `<div class="product-grid" style="grid-template-columns: repeat(${columns}, 1fr)">${cards}</div>`;
}

export function ProductQuickView(props: { product: Product }): string {
    const { product } = props;
    const price = formatPrice(product.price);

    return `
        <div class="quick-view">
            <h4>${product.name}</h4>
            <p>${price}</p>
            <p>${product.description || "No description available"}</p>
        </div>
    `;
}

function getCategoryLabel(category: ProductCategory): string {
    const labels: Record<ProductCategory, string> = {
        [ProductCategory.Electronics]: "Electronics",
        [ProductCategory.Clothing]: "Clothing",
        [ProductCategory.Food]: "Food & Drink",
        [ProductCategory.Books]: "Books",
        [ProductCategory.Other]: "Other",
    };
    return labels[category] || "Unknown";
}
