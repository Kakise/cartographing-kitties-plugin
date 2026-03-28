import { UserService } from "./service";

const service = new UserService();
service.addUser({ name: "Alice", email: "alice@example.com" });
const user = service.getUser("Alice");
