{ config, pkgs, lib, ... }:
{
  # Generated from Ansible playbook using Dozer approach
  # Syscall analysis identified equivalent NixOS modules

  environment.systemPackages = with pkgs; [
    golang-go
    nginx
    nodejs
    npm
    python3
    python3-pip
    redis
  ];

  users.users = {
    gateway = {
      isNormalUser = true;
      createHome = false;
      shell = pkgs.false;
      description = "{{ item | title }} Service User";
    };
    auth = {
      isNormalUser = true;
      createHome = false;
      shell = pkgs.false;
      description = "{{ item | title }} Service User";
    };
    users = {
      isNormalUser = true;
      createHome = false;
      shell = pkgs.false;
      description = "{{ item | title }} Service User";
    };
    orders = {
      isNormalUser = true;
      createHome = false;
      shell = pkgs.false;
      description = "{{ item | title }} Service User";
    };
    notifications = {
      isNormalUser = true;
      createHome = false;
      shell = pkgs.false;
      description = "{{ item | title }} Service User";
    };
  };

  systemd.services = {
    nginx = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
    redis = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
    auth = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
    users = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
    orders = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
    notifications = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
  };

  environment.etc = {
    "nginx/sites-available/api-gateway" = {
      text = ''
        upstream auth_service {
            server 127.0.0.1:3001;
        }
        
        upstream users_service {
            server 127.0.0.1:3002;
        }
        
        upstream orders_service {
            server 127.0.0.1:3003;
        }
        
        upstream notifications_service {
            server 127.0.0.1:3004;
        }
        
        server {
            listen 80;
            server_name api.example.com;
            
            # Rate limiting
            limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
            limit_req zone=api burst=20 nodelay;
            
            # Health check
            location /health {
                return 200 "OK";
                add_header Content-Type text/plain;
            }
            
            # Authentication service
            location /api/auth/ {
                proxy_pass http://auth_service/;
                include proxy_params;
            }
            
            # Users service
            location /api/users/ {
                proxy_pass http://users_service/;
                include proxy_params;
                auth_request /auth;
            }
            
            # Orders service  
            location /api/orders/ {
                proxy_pass http://orders_service/;
                include proxy_params;
                auth_request /auth;
            }
            
            # Notifications service
            location /api/notifications/ {
                proxy_pass http://notifications_service/;
                include proxy_params;
                auth_request /auth;
            }
            
            # Internal auth check
            location = /auth {
                internal;
                proxy_pass http://auth_service/verify;
                proxy_pass_request_body off;
                proxy_set_header Content-Length "";
                proxy_set_header X-Original-URI $request_uri;
            }
        }
      '';
      mode = "0644";
    };
    "nginx/sites-enabled/api-gateway" = {
      source = "/etc/nginx/sites-available/api-gateway";
    };
    "systemd/system/{{ item.user }}.service" = {
      text = ''
        [Unit]
        Description={{ item.name }} Service
        After=network.target {{ item.after | default('') }}
        
        [Service]
        Type=simple
        User={{ item.user }}
        Group={{ item.user }}
        WorkingDirectory=/opt/{{ item.user }}
        ExecStart={{ item.command }}
        Restart=always
        RestartSec=10
        Environment={{ item.env | default('') }}
        
        [Install]
        WantedBy=multi-user.target
      '';
      mode = "0644";
    };
    "service-registry.yml" = {
      text = ''
        # Service Registry Configuration
        services:
          auth:
            host: localhost
            port: 3001
            health_check: /health
            tags: [auth, security]
          
          users:
            host: localhost
            port: 3002
            health_check: /health
            tags: [users, data]
          
          orders:
            host: localhost
            port: 3003
            health_check: /health
            tags: [orders, business]
          
          notifications:
            host: localhost
            port: 3004
            health_check: /health
            tags: [notifications, messaging]
      '';
      mode = "0644";
    };
    "logrotate.d/microservices" = {
      text = ''
        /var/log/microservices-health.log {
            daily
            missingok
            rotate 30
            compress
            delaycompress
            notifempty
            copytruncate
        }
      '';
      mode = "0644";
    };
  };

  systemd.timers = {
    microservices-health-check = {
      description = "Microservices health check";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "daily";
      };
      serviceConfig = {
        ExecStart = "/usr/local/bin/microservices-health.sh";
      };
    };
  };

}