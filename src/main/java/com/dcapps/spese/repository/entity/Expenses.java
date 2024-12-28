package com.dcapps.spese.repository.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder(toBuilder = true)
@Table(name = "expenses", schema = "spese")
public class Expenses {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", nullable = false)
    private Long id;

    @Column(name = "\"name\"", nullable = false, length = 255)
    private String name;

    @Column(name = "amount", nullable = false, precision = 10, scale = 2)
    @Builder.Default
    private BigDecimal amount = BigDecimal.ZERO;

    @Column(name = "creation_date", nullable = false)
    private LocalDateTime creationDate;

    @Column(name = "owner", nullable = false)
    private Long owner;

    @Column(name = "update_date")
    private LocalDateTime updateDate;

    @Column(name = "expense_date")
    private LocalDateTime expenseDate;

    @Column(name = "modified_by")
    private Long modifiedBy;

    @Column(name = "expense_list_id", nullable = false)
    private Long expenseListId;

}

