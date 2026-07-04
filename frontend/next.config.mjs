/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  output: 'standalone',
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ['172.18.0.1', '127.0.0.1', 'localhost'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/:path*`,
      },
    ]
  },
}

export default nextConfig
