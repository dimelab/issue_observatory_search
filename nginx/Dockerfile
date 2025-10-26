# Nginx Dockerfile for production
FROM nginx:1.25-alpine

# Remove default configuration
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom configuration
COPY nginx.conf /etc/nginx/conf.d/app.conf

# Create directories for SSL certificates
RUN mkdir -p /etc/letsencrypt/live/your-domain

# Create directory for Let's Encrypt challenges
RUN mkdir -p /var/www/certbot

# Set proper permissions
RUN chown -R nginx:nginx /var/www/certbot

# Expose ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
