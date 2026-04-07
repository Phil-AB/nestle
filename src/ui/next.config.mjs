/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  experimental: {
    // Document extraction + validation can take several minutes.
    // Raise the proxy timeout so Next.js doesn't 500 before the backend responds.
    proxyTimeout: 600000, // 10 minutes
  },
  images: {
    unoptimized: true,
    domains: ['localhost'],
  },

  // API Proxy Configuration — forwards /api/* to FastAPI backend.
  //
  // The browser always uses RELATIVE paths (/api/v1/...).
  // Next.js server-side rewrites forward those to the actual backend.
  // This means port 8000 never needs to be exposed externally — only
  // port 3000 (the UI) needs to be publicly accessible.
  //
  // Backend URL is controlled by API_BACKEND_URL (server-side only, not
  // sent to the browser). NEXT_PUBLIC_API_URL is intentionally left empty
  // so the browser client uses relative URLs that go through this proxy.
  async rewrites() {
    const backendUrl =
      process.env.API_BACKEND_URL ||          // explicit server-side override
      'http://localhost:8000'                  // default: same machine

    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        source: '/api/v2/:path*',
        destination: `${backendUrl}/api/v2/:path*`,
      },
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ]
  },

  // NEXT_PUBLIC_API_URL is intentionally NOT set here so that the browser
  // uses the "/api/v1" relative fallback in api-client.ts, routing through
  // the proxy above instead of connecting directly to port 8000.
  env: {
    NEXT_PUBLIC_API_KEY: process.env.NEXT_PUBLIC_API_KEY || 'dev-key-12345',
  },

  // Optimize for production
  swcMinify: true,
  reactStrictMode: true,
}

export default nextConfig
