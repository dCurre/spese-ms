package com.dcapps.spese.feature.spese;

import com.dcapps.spese.repository.ExpensesListsRepository;
import com.dcapps.spese.repository.ExpensesRepository;
import com.dcapps.spese.repository.entity.Expenses;
import com.dcapps.spese.repository.entity.ExpensesLists;
import lombok.AllArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@AllArgsConstructor
public class SpeseService {

    private final ExpensesRepository expensesRepository;
    private final ExpensesListsRepository expensesListsRepository;

    public List<Expenses> getExpenses() {
        return expensesRepository.findAll();
    }

    public List<ExpensesLists> getExpensesLists() {
        return expensesListsRepository.findAll();
    }
}
