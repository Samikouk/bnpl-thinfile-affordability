/** Resolve the signed-in analyst. Never invent a fallback name. */
export function actorEmail(
  forwardedEmail: string | undefined,
  envUser: string | undefined,
): string | undefined {
  const forwarded = forwardedEmail?.trim();
  if (forwarded && forwarded.includes('@')) {
    return forwarded;
  }
  const env = envUser?.trim();
  if (env && env.includes('@')) {
    return env;
  }
  return undefined;
}
