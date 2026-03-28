/**
 * User-related type definitions.
 */

export interface Address {
    street: string;
    city: string;
    state: string;
    zipCode: string;
}

export interface User {
    id: number;
    name: string;
    email: string;
    address?: Address;
    isActive: boolean;
    createdAt: string;
}

export type UserID = number;

export interface CreateUserRequest {
    name: string;
    email: string;
    address?: Address;
}

export interface UpdateUserRequest {
    name?: string;
    email?: string;
    address?: Address;
}

export function isValidUser(user: unknown): user is User {
    if (typeof user !== "object" || user === null) return false;
    const u = user as Record<string, unknown>;
    return typeof u.id === "number" && typeof u.name === "string" && typeof u.email === "string";
}

export function formatUserDisplayName(user: User): string {
    return user.name
        .split(" ")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
        .join(" ");
}
