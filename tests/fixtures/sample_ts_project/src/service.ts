import { User, UserID } from "./types";

export class UserService {
    private users: Map<UserID, User> = new Map();

    addUser(user: User): void {
        this.users.set(user.name, user);
    }

    getUser(name: string): User | undefined {
        return this.users.get(name);
    }
}
