package com.dcapps.spese.feature.spese;

import com.dcapps.spese.repository.entity.Expenses;
import com.dcapps.spese.repository.entity.ExpensesLists;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.AllArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@AllArgsConstructor
@RequestMapping("/spese")
@Tag(name = "Spese Controller", description = "APIs for managing expenses")
public class SpeseController {

    private final SpeseService speseService;

    @Operation(
            summary = "Get all expenses",
            description = "Retrieves all expenses"
    )
    @GetMapping("/expenses")
    public List<Expenses> getExpenses() {
        return speseService.getExpenses();
    }

    @Operation(
            summary = "Get all expenses lists",
            description = "Retrieves all expenses lists"
    )
    @GetMapping("/expenses-lists")
    public List<ExpensesLists> getExpensesLists() {
        return speseService.getExpensesLists();
    }

}
