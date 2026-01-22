package com.rohan.perfguard_demo_java.controller;

import com.rohan.perfguard_demo_java.service.PerfDemoService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

@RestController
public class PerfDemoController {

    private final PerfDemoService service;

    public PerfDemoController(PerfDemoService service) {
        this.service = service;
    }

    @GetMapping("/unique")
    public List<Integer> unique(@RequestParam String values) {
        List<Integer> input = Arrays.stream(values.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .map(Integer::parseInt)
                .collect(Collectors.toList());

        return service.uniquePreserveOrder(input);
    }
}