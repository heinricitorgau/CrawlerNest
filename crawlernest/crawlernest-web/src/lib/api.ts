const DEFAULT_API_BASE_URL = "http://localhost:8080";

export function getApiBaseUrl(): string {
  return (
    process.env.API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    DEFAULT_API_BASE_URL
  );
}

type NextRequestInit = RequestInit & { next?: { revalidate?: number } };

export async function fetchJson<T>(
  path: string,
  init?: NextRequestInit
): Promise<T> {
  const res = await fetch(`${getApiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    next: {
      revalidate: 0,
      ...(init?.next || {}),
    },
  });

  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export async function fetchAppJson<T>(
  path: string,
  init?: NextRequestInit
): Promise<T> {
  const res = await fetch(path, {
    ...init,
    cache: "no-store",
    next: {
      revalidate: 0,
      ...(init?.next || {}),
    },
  });

  if (!res.ok) {
    throw new Error(`Request failed with status ${res.status}`);
  }

  return res.json() as Promise<T>;
}
