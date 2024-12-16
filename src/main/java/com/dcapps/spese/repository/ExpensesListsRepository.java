package com.dcapps.spese.repository;

import com.dcapps.spese.repository.entity.ExpensesLists;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ExpensesListsRepository extends JpaRepository<ExpensesLists, Long> {
}
