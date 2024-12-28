package com.dcapps.spese.feature.spese;

import com.dcapps.spese.feature.spese.contract.CreateExpensesListRequestDto;
import com.dcapps.spese.feature.spese.contract.CreateExpensesRequestDto;
import com.dcapps.spese.feature.spese.contract.UpdateExpensesRequestDto;
import com.dcapps.spese.repository.entity.Expenses;
import com.dcapps.spese.repository.entity.ExpensesLists;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@AllArgsConstructor
@RequestMapping("/spese")
public class SpeseController {

    private final SpeseService speseService;

    @Operation(
            summary = "Get all expenses",
            description = "Retrieves all expenses or a list of expenses by list id",
            tags = "Expenses"
    )
    @GetMapping("/expenses")
    public List<Expenses> getExpenses(
            @RequestParam("list-id")
            @Min(value = 1, message = "list id must be greater than 1")
            Long listId
    ) {
        return speseService.getExpenses(listId);
    }

    @Operation(
            summary = "Post expense",
            description = "Creates an expense",
            tags = "Expenses"
    )
    @PostMapping("/expenses")
    public String postExpense(@Valid @RequestBody CreateExpensesRequestDto requestDto) {
        return speseService.postExpense(requestDto);
    }

    @Operation(
            summary = "Update expense",
            description = "Updates an expense",
            tags = "Expenses"
    )
    @PutMapping("/expenses")
    public String updateExpense(@Valid @RequestBody UpdateExpensesRequestDto requestDto) {
        return speseService.updateExpense(requestDto);
    }

    @Operation(
            summary = "Deletes expenses",
            description = "Deletes an expense by id",
            tags = "Expenses"
    )
    @DeleteMapping("/expenses")
    public String deleteExpense(
            @RequestParam("id")
            @NotNull(message = "list id cannot be null")
            @Min(value = 1, message = "list id must be greater than 1")
            Long id
    ) {
        return speseService.deleteExpense(id);
    }

    @Operation(
            summary = "Get all expenses lists",
            description = "Retrieves all expenses lists",
            tags = "Expenses Lists"
    )
    @GetMapping("/expenses-lists")
    public List<ExpensesLists> getExpensesLists() {
        return speseService.getExpensesLists();
    }

    @Operation(
            summary = "Post expenses lists",
            description = "Creates an expenses list",
            tags = "Expenses Lists"
    )
    @PostMapping("/expenses-lists")
    public String postExpensesLists(@Valid @RequestBody CreateExpensesListRequestDto requestDto) {
        return speseService.postExpensesLists(requestDto);
    }

    @Operation(
            summary = "Deletes expenses lists",
            description = "Deletes an expenses lists and all its related expenses",
            tags = "Expenses Lists"
    )
    @DeleteMapping("/expenses-lists")
    public String deleteExpensesLists(
            @RequestParam("list-id")
            @NotNull(message = "list id cannot be null")
            @Min(value = 1, message = "list id must be greater than 1")
            Long listId
    ) {
        return speseService.deleteExpensesLists(listId);
    }

}
