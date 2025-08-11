{ config, pkgs, lib, ... }:
{
  # Generated from Ansible playbook using Dozer approach
  # Syscall analysis identified equivalent NixOS modules

  environment.systemPackages = with pkgs; [
    docker
    git
    golang-go
    jenkins
    nginx
    nodejs
    npm
    openjdk-11-jdk
    python3
    python3-pip
  ];

  users.users = {
    {{ item.name }} = {
      isNormalUser = true;
      createHome = "{{ item.createhome }}";
      extraGroups = "{{ item.groups }}";
      shell = pkgs.{{ item.shell }};
      description = "{{ item.comment }}";
    };
  };

  systemd.services = {
    docker = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
    jenkins = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
    nginx = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
    webhook-listener = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
  };

  environment.etc = {
    "default/jenkins" = {
      text = ''
        # Jenkins Configuration
        JENKINS_HOME=/opt/jenkins
        JENKINS_USER=jenkins
        JENKINS_GROUP=jenkins
        JENKINS_WAR=/usr/share/jenkins/jenkins.war
        JENKINS_LOG=/var/log/jenkins/jenkins.log
        JAVA_ARGS="-Djava.awt.headless=true -Xmx2048m"
        JENKINS_ARGS="--webroot=/var/cache/jenkins/war --httpPort=8080"
      '';
      mode = "0644";
    };
    "systemd/system/jenkins.service" = {
      text = ''
        [Unit]
        Description=Jenkins Continuous Integration Server
        After=network.target
        
        [Service]
        Type=notify
        NotifyAccess=main
        ExecStart=/usr/bin/java $JAVA_ARGS -jar $JENKINS_WAR $JENKINS_ARGS
        Restart=on-failure
        RestartSec=5
        User=jenkins
        Group=jenkins
        Environment=JENKINS_HOME=/opt/jenkins
        
        [Install]
        WantedBy=multi-user.target
      '';
      mode = "0644";
    };
    "nginx/sites-available/cicd-dashboard" = {
      text = ''
        server {
            listen 80;
            server_name cicd.example.com;
            
            # Jenkins
            location /jenkins/ {
                proxy_pass http://127.0.0.1:8080/jenkins/;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
            
            # Docker Registry UI
            location /registry/ {
                proxy_pass http://127.0.0.1:5000/;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
            }
            
            # Artifacts
            location /artifacts/ {
                alias /opt/artifacts/;
                autoindex on;
                autoindex_exact_size off;
                autoindex_localtime on;
            }
            
            # Status page
            location / {
                return 301 /jenkins/;
            }
        }
      '';
      mode = "0644";
    };
    "nginx/sites-enabled/cicd-dashboard" = {
      source = "/etc/nginx/sites-available/cicd-dashboard";
    };
    "systemd/system/webhook-listener.service" = {
      text = ''
        [Unit]
        Description=GitHub Webhook Listener
        After=network.target
        
        [Service]
        Type=simple
        User=jenkins
        Group=jenkins
        ExecStart=/usr/bin/python3 /opt/webhook-listener.py
        Restart=always
        RestartSec=5
        
        [Install]
        WantedBy=multi-user.target
      '';
      mode = "0644";
    };
    "logrotate.d/cicd" = {
      text = ''
        /var/log/jenkins/*.log {
            daily
            missingok
            rotate 30
            compress
            delaycompress
            notifempty
            copytruncate
        }
        
        /tmp/builds/**/logs/*.log {
            daily
            missingok
            rotate 7
            compress
            delaycompress
            notifempty
            copytruncate
        }
      '';
      mode = "0644";
    };
  };

}