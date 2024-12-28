package com.dcapps.spese.feature.spese.contract;


import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class CreateExpensesListRequestDto {

    @NotNull
    @NotEmpty
    @Size(min = 1, max = 30, message = "Name must be between 1 and 30 characters")
    private String name;

    @NotNull
    @Min(1)
    private Long owner;

}
