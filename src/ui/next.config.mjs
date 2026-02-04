/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
    domains: ['localhost'],
  },

  // API Proxy Configuration - forwards /api/* to FastAPI backend
  async rewrites() {
    // Read from .env.local or use default (public IP for cloud, localhost for dev)
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://54.87.52.48:8000/api/v1'
    const baseUrl = apiUrl.replace('/api/v1', '')

    return [
      {
        source: '/api/v1/:path*',
        destination: `${baseUrl}/api/v1/:path*`,
      },
      {
        source: '/api/v2/:path*',
        destination: `${baseUrl}/api/v2/:path*`,
      },
      {
        source: '/api/:path*',
        destination: `${baseUrl}/api/v1/:path*`,
      },
    ]
  },

  // Make environment variables available
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
    NEXT_PUBLIC_API_KEY: process.env.NEXT_PUBLIC_API_KEY || 'dev-key-12345',
  },

  // Optimize for production
  swcMinify: true,
  reactStrictMode: true,
}

export default nextConfig
