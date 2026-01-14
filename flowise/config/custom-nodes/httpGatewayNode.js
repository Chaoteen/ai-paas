// 自定义节点：AIOS平台网关调用节点
// 该节点将Flowise的数据发送至您编写的Prompt Execution Gateway

module.exports = function (RED) {
    class HttpGatewayNode {
        constructor(config) {
            RED.nodes.createNode(this, config);
            
            // 从节点配置中获取参数
            this.gatewayUrl = config.gatewayUrl;
            this.tenantId = config.tenantId;
            this.sessionId = config.sessionId;
            this.agentProfile = config.agentProfile;
            
            // 处理输入消息
            this.on('input', async (msg, send, done) => {
                try {
                    // 构建发送给网关的请求负载
                    const requestPayload = {
                        tenant_id: this.tenantId || msg.tenant_id,
                        session_id: this.sessionId || msg.session_id,
                        user_message: msg.payload, // 主输入作为用户消息
                        variables: msg.variables || {}, // 支持额外变量
                        agent_profile: this.agentProfile || msg.agent_profile,
                        request_source: 'flowise' // 标识请求来源
                    };

                    this.log(`正在向网关发送请求: ${this.gatewayUrl}`);
                    
                    // 调用网关API
                    const response = await fetch(this.gatewayUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${this.credentials?.apiKey}`
                        },
                        body: JSON.stringify(requestPayload)
                    });

                    if (!response.ok) {
                        throw new Error(`网关响应错误: ${response.status} ${response.statusText}`);
                    }

                    const responseData = await response.json();
                    
                    // 将网关返回的结果传递给下一个节点
                    msg.payload = responseData.result || responseData;
                    msg.usage = responseData.usage || {};
                    msg.metadata = responseData.metadata || {};
                    
                    send(msg);
                    done();
                    
                } catch (error) {
                    this.error(`网关调用失败: ${error.message}`, msg);
                    done(error);
                }
            });
        }
    }

    // 注册节点类型
    RED.nodes.registerType("aios-gateway-call", HttpGatewayNode, {
        credentials: {
            apiKey: { type: "password" } // 安全地存储API密钥
        }
    });
};