package com.dcapps.spese.feature.spese.contract;


import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.experimental.SuperBuilder;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@SuperBuilder(toBuilder = true)
public class BaseExpensesRequestDto {

    @NotNull
    @NotEmpty
    @Size(min = 1, max = 20, message = "Name must be between 1 and 20 characters")
    private String name;

    @NotNull
    private BigDecimal amount;

    @NotNull
    private LocalDateTime expenseDate;

    @NotNull
    @Min(value = 1)
    private Long listId;

}
