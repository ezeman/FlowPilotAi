export const PLATFORM_OWNER_ROLES = ["platform_owner", "platform_admin"];

export function isPlatformOwner(userOrRole) {
  const role = typeof userOrRole === "string" ? userOrRole : userOrRole?.role;
  return PLATFORM_OWNER_ROLES.includes(role);
}

export function roleLabel(role) {
  if (PLATFORM_OWNER_ROLES.includes(role)) return "Platform Owner";
  if (role === "subscriber_admin") return "Subscriber Admin";
  if (role === "editor") return "Editor";
  return role || "Editor";
}
