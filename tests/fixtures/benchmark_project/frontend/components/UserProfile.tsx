/**
 * UserProfile component for displaying user information.
 */

import { User, formatUserDisplayName, isValidUser } from "../types/user";
import { Order } from "../types/order";
import { AuthService } from "../services/auth";

export interface UserProfileProps {
    user: User;
    orders?: Order[];
    onEdit?: (user: User) => void;
    onLogout?: () => void;
}

export function UserProfile(props: UserProfileProps): string {
    const { user, orders = [], onEdit, onLogout } = props;
    const displayName = formatUserDisplayName(user);

    const orderCount = orders.length;
    const totalSpent = orders.reduce((sum, order) => sum + order.total, 0);

    return `
        <div class="user-profile">
            <h2>${displayName}</h2>
            <p>${user.email}</p>
            <p>Status: ${user.isActive ? "Active" : "Inactive"}</p>
            ${user.address ? `<p>Address: ${user.address.street}, ${user.address.city}</p>` : ""}
            <div class="stats">
                <span>Orders: ${orderCount}</span>
                <span>Total Spent: $${totalSpent.toFixed(2)}</span>
            </div>
        </div>
    `;
}

export function UserAvatar(props: { user: User; size?: number }): string {
    const { user, size = 40 } = props;
    const initials = user.name
        .split(" ")
        .map((p) => p[0])
        .join("")
        .toUpperCase();

    return `<div class="avatar" style="width:${size}px;height:${size}px">${initials}</div>`;
}

export function UserBadge(props: { user: User }): string {
    const { user } = props;
    return `<span class="badge ${user.isActive ? "active" : "inactive"}">${user.name}</span>`;
}
