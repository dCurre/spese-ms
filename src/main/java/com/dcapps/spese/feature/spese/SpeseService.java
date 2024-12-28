package com.dcapps.spese.feature.spese;

import com.dcapps.spese.feature.spese.contract.CreateExpensesListRequestDto;
import com.dcapps.spese.feature.spese.contract.CreateExpensesRequestDto;
import com.dcapps.spese.feature.spese.contract.UpdateExpensesRequestDto;
import com.dcapps.spese.repository.ExpensesListsRepository;
import com.dcapps.spese.repository.ExpensesRepository;
import com.dcapps.spese.repository.entity.Expenses;
import com.dcapps.spese.repository.entity.ExpensesLists;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Service
@AllArgsConstructor
public class SpeseService {

    private final ExpensesRepository expensesRepository;
    private final ExpensesListsRepository expensesListsRepository;

    public List<Expenses> getExpenses(final Long listId) {

        return
                listId != null
                ? expensesRepository.findByExpenseListIdOrderByCreationDateAsc(listId)
                : expensesRepository.findAll();

    }

    public String postExpense(final CreateExpensesRequestDto requestDto) {

        Expenses expense =
                Expenses.builder()
                        .name(requestDto.getName())
                        .amount(requestDto.getAmount())
                        .expenseDate(requestDto.getExpenseDate())
                        .owner(requestDto.getOwner())
                        .expenseListId(requestDto.getListId())
                        .creationDate(LocalDateTime.now())
                        .build();

        expensesRepository.save(expense);

        return "success";

    }

    public String updateExpense(final UpdateExpensesRequestDto requestDto) {

        Optional<Expenses> expense = expensesRepository.findById(requestDto.getId());

        if(expense.isEmpty()) {
            return String.format("Expense with id %s not found", requestDto.getId());
        }

        expensesRepository.save(
                expense.get().toBuilder()
                        .name(requestDto.getName())
                        .amount(requestDto.getAmount())
                        .expenseDate(requestDto.getExpenseDate())
                        .expenseListId(requestDto.getListId())
                        .updateDate(LocalDateTime.now())
                        .build()
        );

        return "success";

    }

    public String deleteExpense(final Long id) {

        expensesRepository.deleteById(id);

        return "success";

    }

    public List<ExpensesLists> getExpensesLists() {
        return expensesListsRepository.findAll();
    }

    public String postExpensesLists(final CreateExpensesListRequestDto requestDto) {

        ExpensesLists newList =
                ExpensesLists.builder()
                        .name(requestDto.getName())
                        .ownerId(requestDto.getOwner())
                        .creationDate(LocalDateTime.now())
                        .build();

        expensesListsRepository.save(newList);

        return "success";
    }

    public String deleteExpensesLists(final Long listId) {

        expensesListsRepository.deleteById(listId);

        return "success";
    }
}
