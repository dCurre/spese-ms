package com.dcapps.spese.feature.spese.contract;


import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.SuperBuilder;

@EqualsAndHashCode(callSuper = true)
@Data
@SuperBuilder(toBuilder = true)
public class UpdateExpensesRequestDto extends BaseExpensesRequestDto {

    @NotNull
    @Min(value = 1)
    private Long id;

}
