package com.dcapps.spese.config;

import io.swagger.v3.oas.annotations.OpenAPIDefinition;
import io.swagger.v3.oas.annotations.info.Info;
import org.springframework.context.annotation.Configuration;

@OpenAPIDefinition(
    info = @Info(
        title = "Spese",
        version = "1.0",
        description = "API documentation"
    )
)
@Configuration
public class SwaggerConfig {
    // Additional Swagger configuration if needed
}