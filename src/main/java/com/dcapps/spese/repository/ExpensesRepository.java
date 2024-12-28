package com.dcapps.spese.repository;

import com.dcapps.spese.repository.entity.Expenses;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ExpensesRepository extends JpaRepository<Expenses, Long> {

    List<Expenses> findByExpenseListIdOrderByCreationDateAsc(Long listId);
}
